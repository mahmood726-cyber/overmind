"""Supervised drain loop (drain robustness — item 1).

Wraps a per-vendor drain worker so it becomes a SUPERVISED loop:
  * writes a heartbeat every iteration (liveness readable from a file),
  * AUTO-RESTARTS on an unexpected worker exception (bounded by ``max_restarts``),
  * on a usage cap (detected via ``QuotaTracker`` hints in the worker output),
    records the cap to the cap-log with a reset timestamp and BACKS OFF (sleeps
    to reset) instead of hammering the seat.

Goal: vendors keep draining without any interactive session staying awake, and
cap/reset times land in a machine-readable log. Clock + sleep are injectable so
the whole supervisor is deterministically testable without real waiting.

This is the harness-side primitive the external Dispatch drain loops adopt; it
does not itself spawn vendor processes (the worker callable does that), so it is
side-effect-free to import.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from overmind.reliability.cap_log import CapLog
from overmind.reliability.heartbeat import (
    CAPPED,
    IDLE,
    RESTARTING,
    RUNNING,
    STOPPED,
    HeartbeatFile,
)
from overmind.runners.quota_tracker import QuotaTracker

# A worker runs one drain step and returns the output lines it produced (used for
# cap detection). It may raise on failure; the supervisor handles restart.
Worker = Callable[[], "list[str] | None"]


@dataclass(slots=True)
class SupervisorResult:
    loop: str
    iterations: int = 0
    restarts: int = 0
    caps: int = 0
    stopped_reason: str = ""
    cap_messages: list[str] = field(default_factory=list)


class SupervisedLoop:
    def __init__(
        self,
        name: str,
        worker: Worker,
        *,
        seat: str = "",
        heartbeat: HeartbeatFile,
        cap_log: CapLog,
        quota: QuotaTracker | None = None,
        max_restarts: int = 3,
        cap_backoff_seconds: float = 1800.0,   # 30 min default sleep-to-reset
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.name = name
        self.worker = worker
        self.seat = seat or name
        self.heartbeat = heartbeat
        self.cap_log = cap_log
        self.quota = quota or QuotaTracker()
        self.max_restarts = max_restarts
        self.cap_backoff_seconds = cap_backoff_seconds
        self._sleep = sleep
        self._clock = clock

    def run(self, *, max_iterations: int | None = None) -> SupervisorResult:
        """Drive the worker in a supervised loop.

        ``max_iterations`` bounds the loop (tests / a single batch). In production
        the caller passes a large bound or loops externally; the supervisor never
        blocks a session because the only sleep is the cap back-off.
        """
        result = SupervisorResult(loop=self.name)
        restarts = 0
        i = 0
        while max_iterations is None or i < max_iterations:
            i += 1
            result.iterations = i
            self.heartbeat.beat(self.name, RUNNING, iteration=i)
            try:
                output = self.worker()
            except Exception as exc:  # noqa: BLE001 — supervise: restart, don't crash
                restarts += 1
                result.restarts = restarts
                self.heartbeat.beat(self.name, RESTARTING, detail=f"{type(exc).__name__}: {exc}"[:200], iteration=i)
                if restarts > self.max_restarts:
                    result.stopped_reason = f"max_restarts ({self.max_restarts}) exceeded"
                    self.heartbeat.beat(self.name, STOPPED, detail=result.stopped_reason, iteration=i)
                    return result
                continue

            lines = list(output or [])
            if self.quota.detect_rate_limit(lines):
                cap_msg = next(
                    (ln for ln in lines if any(h in ln.lower() for h in ("limit", "quota", "capacity", "overloaded"))),
                    "usage cap detected",
                )[:200]
                result.caps += 1
                result.cap_messages.append(cap_msg)
                reset_at = self._clock() + self.cap_backoff_seconds
                self.cap_log.record_cap(self.seat, cap_msg, detected_at=self._clock(), reset_at=reset_at)
                self.heartbeat.beat(self.name, CAPPED, detail=cap_msg, iteration=i)
                self._sleep(self.cap_backoff_seconds)  # sleep-to-reset; no session stays awake
                self.cap_log.record_reset(self.seat)   # mark recovered after back-off
        result.stopped_reason = result.stopped_reason or "completed"
        self.heartbeat.beat(self.name, IDLE, iteration=i)
        return result
