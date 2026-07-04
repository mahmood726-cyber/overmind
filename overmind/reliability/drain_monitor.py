"""Truthful drain monitor (monitoring — item 2).

The agent-drain-watchdog's blind spot: it inspected sessions only, so a loop that
had silently died (or a seat silently capped) read as "fine" — a false negative.
This monitor reads the FILES the supervised loops write — heartbeat files + the
cap-log — so drain state is observed from ground truth, not inferred from a live
session that may not exist.

Recommendation encoded here (see harness/RELIABILITY.md): the orchestrator can
consume ``DrainMonitor.report()`` directly and the session-only watchdog can be
retired — a monitor that reads state files cannot have the session-inspection
false-negative.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from overmind.reliability.cap_log import CapLog
from overmind.reliability.heartbeat import HeartbeatFile

DEFAULT_STALE_AFTER_SECONDS = 900.0   # 15 min without a heartbeat => stale/dead


@dataclass(slots=True)
class LoopStatus:
    loop: str
    status: str
    age_seconds: float | None
    stale: bool
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "loop": self.loop,
            "status": self.status,
            "age_seconds": None if self.age_seconds is None else round(self.age_seconds, 1),
            "stale": self.stale,
            "detail": self.detail,
        }


@dataclass(slots=True)
class DrainReport:
    loops: list[LoopStatus] = field(default_factory=list)
    capped_seats: dict[str, dict] = field(default_factory=dict)

    @property
    def stale_loops(self) -> list[str]:
        return [l.loop for l in self.loops if l.stale]

    @property
    def healthy(self) -> bool:
        return not self.stale_loops and not self.capped_seats

    def to_dict(self) -> dict:
        return {
            "healthy": self.healthy,
            "loops": [l.to_dict() for l in self.loops],
            "stale_loops": self.stale_loops,
            "capped_seats": self.capped_seats,
        }

    def headline(self) -> str:
        return (
            f"drain: {len(self.loops)} loops, {len(self.stale_loops)} stale "
            f"({', '.join(self.stale_loops) or 'none'}); "
            f"{len(self.capped_seats)} seats capped "
            f"({', '.join(self.capped_seats) or 'none'})"
        )


class DrainMonitor:
    """Reads heartbeat files + the cap-log and reports truthful drain state."""

    def __init__(
        self,
        heartbeat_dir: Path | str,
        cap_log: CapLog,
        *,
        stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
        clock: Callable[[], float] = time.time,
        heartbeat_glob: str = "*.hb.json",
    ) -> None:
        self.heartbeat_dir = Path(heartbeat_dir)
        self.cap_log = cap_log
        self.stale_after_seconds = stale_after_seconds
        self._clock = clock
        self._glob = heartbeat_glob

    def loop_statuses(self) -> list[LoopStatus]:
        statuses: list[LoopStatus] = []
        if not self.heartbeat_dir.exists():
            return statuses
        for hb_path in sorted(self.heartbeat_dir.glob(self._glob)):
            hbf = HeartbeatFile(hb_path, clock=self._clock)
            hb = hbf.read()
            if hb is None:
                continue
            age = hbf.age_seconds()
            stale = age is None or age > self.stale_after_seconds
            statuses.append(LoopStatus(
                loop=hb.loop or hb_path.stem, status=hb.status,
                age_seconds=age, stale=stale, detail=hb.detail,
            ))
        return statuses

    def report(self) -> DrainReport:
        now = self._clock()
        capped = {
            seat: {"cap_message": ev.cap_message, "detected_at": ev.detected_at, "reset_at": ev.reset_at}
            for seat, ev in self.cap_log.active_caps(now=now).items()
        }
        return DrainReport(loops=self.loop_statuses(), capped_seats=capped)
