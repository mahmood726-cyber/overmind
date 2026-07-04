"""Single machine-readable cap-log for vendor usage caps (drain robustness — item 1).

When a vendor seat hits a usage cap, the loop records a cap event here — one
append-only JSONL with the cap message + detected/reset timestamps per seat — so
cap and reset times are **readable without any session staying awake**. The drain
monitor (item 2) and the orchestrator read this to know which seats are down and
when they come back.

Documented path (default): ``<data_dir>/reliability/cap_log.jsonl`` (override via
``OVERMIND_CAP_LOG_PATH``). Append-only; ``active_caps`` folds the stream to the
currently-capped seats.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

CAP = "cap"
RESET = "reset"


def default_cap_log_path(data_dir: Path | str | None = None) -> Path:
    override = os.environ.get("OVERMIND_CAP_LOG_PATH")
    if override:
        return Path(override)
    base = Path(data_dir) if data_dir else Path.cwd()
    return base / "reliability" / "cap_log.jsonl"


@dataclass(slots=True)
class CapEvent:
    seat: str
    cap_message: str
    detected_at: float
    reset_at: float | None = None      # epoch seconds when the cap is expected to clear

    def to_dict(self) -> dict:
        return {
            "kind": CAP,
            "seat": self.seat,
            "cap_message": self.cap_message,
            "detected_at": self.detected_at,
            "reset_at": self.reset_at,
        }


class CapLog:
    """Append-only cap-log with a folded ``active_caps`` view."""

    def __init__(self, path: Path | str, *, clock: Callable[[], float] = time.time) -> None:
        self.path = Path(path)
        self._clock = clock

    # --- writers --------------------------------------------------------------
    def record_cap(self, seat: str, cap_message: str, *,
                   detected_at: float | None = None, reset_at: float | None = None) -> CapEvent:
        ev = CapEvent(
            seat=seat,
            cap_message=cap_message[:500],
            detected_at=detected_at if detected_at is not None else self._clock(),
            reset_at=reset_at,
        )
        self._append(ev.to_dict())
        return ev

    def record_reset(self, seat: str, *, at: float | None = None) -> None:
        self._append({"kind": RESET, "seat": seat, "at": at if at is not None else self._clock()})

    def _append(self, record: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    # --- readers --------------------------------------------------------------
    def events(self) -> list[dict]:
        if not self.path.exists():
            return []
        out: list[dict] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    def active_caps(self, now: float | None = None) -> dict[str, CapEvent]:
        """Seats currently capped: latest cap event with no later reset and whose
        ``reset_at`` (if set) is still in the future."""
        now = now if now is not None else self._clock()
        latest_cap: dict[str, CapEvent] = {}
        last_reset_at: dict[str, float] = {}
        for rec in self.events():
            seat = rec.get("seat", "")
            if not seat:
                continue
            if rec.get("kind") == CAP:
                latest_cap[seat] = CapEvent(
                    seat=seat,
                    cap_message=str(rec.get("cap_message", "")),
                    detected_at=float(rec.get("detected_at", 0.0) or 0.0),
                    reset_at=(None if rec.get("reset_at") is None else float(rec["reset_at"])),
                )
            elif rec.get("kind") == RESET:
                last_reset_at[seat] = float(rec.get("at", 0.0) or 0.0)
        active: dict[str, CapEvent] = {}
        for seat, cap in latest_cap.items():
            # cleared by an explicit reset that came after the cap was detected
            if last_reset_at.get(seat, -1.0) >= cap.detected_at:
                continue
            # cleared by its own reset_at having passed
            if cap.reset_at is not None and cap.reset_at <= now:
                continue
            active[seat] = cap
        return active
