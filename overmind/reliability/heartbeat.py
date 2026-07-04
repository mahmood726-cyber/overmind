"""Per-loop heartbeat files (drain robustness — item 1).

Each background drain loop writes a heartbeat file every iteration so a monitor
(or the orchestrator) can tell — *from files, not from session inspection* —
whether the loop is alive, capped, or dead. This is the file the drain monitor
reads to close the watchdog's blind spot (item 2).

Atomic write (temp + ``os.replace``) so a reader never sees a half-written file.
Clock is injectable so staleness logic is deterministically testable.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# Heartbeat statuses.
RUNNING = "running"
CAPPED = "capped"
RESTARTING = "restarting"
STOPPED = "stopped"
IDLE = "idle"


@dataclass(slots=True)
class Heartbeat:
    loop: str
    status: str
    updated_at: float          # epoch seconds
    pid: int = 0
    detail: str = ""
    iteration: int = 0

    def to_dict(self) -> dict:
        return {
            "loop": self.loop,
            "status": self.status,
            "updated_at": self.updated_at,
            "pid": self.pid,
            "detail": self.detail,
            "iteration": self.iteration,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Heartbeat":
        return cls(
            loop=str(d.get("loop", "")),
            status=str(d.get("status", "")),
            updated_at=float(d.get("updated_at", 0.0) or 0.0),
            pid=int(d.get("pid", 0) or 0),
            detail=str(d.get("detail", "")),
            iteration=int(d.get("iteration", 0) or 0),
        )


class HeartbeatFile:
    """Atomic heartbeat writer/reader for one loop."""

    def __init__(self, path: Path | str, *, clock: Callable[[], float] = time.time) -> None:
        self.path = Path(path)
        self._clock = clock

    def beat(self, loop: str, status: str = RUNNING, *, detail: str = "",
             pid: int | None = None, iteration: int = 0) -> Heartbeat:
        hb = Heartbeat(
            loop=loop, status=status, updated_at=self._clock(),
            pid=pid if pid is not None else os.getpid(), detail=detail, iteration=iteration,
        )
        self._atomic_write(hb.to_dict())
        return hb

    def read(self) -> Heartbeat | None:
        if not self.path.exists():
            return None
        try:
            return Heartbeat.from_dict(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, ValueError):
            return None

    def age_seconds(self) -> float | None:
        hb = self.read()
        if hb is None:
            return None
        return max(0.0, self._clock() - hb.updated_at)

    def is_stale(self, max_age_seconds: float) -> bool:
        """True if there is no heartbeat or it is older than ``max_age_seconds``."""
        age = self.age_seconds()
        return age is None or age > max_age_seconds

    def _atomic_write(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + f".tmp{os.getpid()}")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, self.path)
