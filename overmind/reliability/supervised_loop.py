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

# Codex/vendor workspace credits AUTO-REFILL ~5h after an "out of credits" cap.
# This is a TIME-BASED cap (not manual/terminal): the loop parks, re-probes on the
# back-off cadence, and auto-resumes the moment a probe returns a real completion.
CREDIT_REFILL_SECONDS = 5 * 3600.0
# If a seat is STILL out-of-credits past cap_start + this, the 5h rolling refill has
# clearly passed and NOT restored it => the WEEKLY allotment is exhausted (a second,
# longer cap tier). The "out of credits" message is identical, so we distinguish by
# BEHAVIOUR (still-capped-after-5.5h), switch to a long probe cadence, and flag it.
WEEKLY_RECLASSIFY_SECONDS = 5.5 * 3600.0
WEEKLY_PROBE_SECONDS = 3600.0
CREDIT_CAP_HINTS = ("out of credits", "refill", "insufficient_quota", "out of credit")


def _is_credit_cap(text: str) -> bool:
    low = text.lower()
    return any(h in low for h in CREDIT_CAP_HINTS)


@dataclass(slots=True)
class SupervisorResult:
    loop: str
    iterations: int = 0
    restarts: int = 0
    caps: int = 0
    stopped_reason: str = ""
    cap_messages: list[str] = field(default_factory=list)
    weekly_exhausted: bool = False   # seat's weekly allotment gone (5h refill won't help)


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
        cap_backoff_seconds: float = 900.0,    # re-probe cadence (~15 min) while capped
        credit_refill_seconds: float = CREDIT_REFILL_SECONDS,  # 5h auto-refill for out-of-credits
        weekly_reclassify_seconds: float = WEEKLY_RECLASSIFY_SECONDS,  # >this still-capped => weekly
        weekly_probe_seconds: float = WEEKLY_PROBE_SECONDS,    # hourly probe once weekly-exhausted
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
        self.credit_refill_seconds = credit_refill_seconds
        self.weekly_reclassify_seconds = weekly_reclassify_seconds
        self.weekly_probe_seconds = weekly_probe_seconds
        self._sleep = sleep
        self._clock = clock
        self._cap_start: float | None = None   # stable cap-start epoch across re-probes

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
            is_credit = any(_is_credit_cap(ln) for ln in lines)
            if self.quota.detect_rate_limit(lines) or is_credit:
                cap_msg = next(
                    (ln for ln in lines if _is_credit_cap(ln)
                     or any(h in ln.lower() for h in ("limit", "quota", "capacity", "overloaded"))),
                    "usage cap detected",
                )[:200]
                result.caps += 1
                result.cap_messages.append(cap_msg)
                # Stable cap-start across re-probes so the expected reset does not drift.
                if self._cap_start is None:
                    self._cap_start = self._clock()
                elapsed = self._clock() - self._cap_start
                # TWO-TIER credit cap: (1) 5h rolling window; (2) WEEKLY allotment, which
                # the 5h refill does NOT restore -- detected by still-capped past +5.5h.
                if is_credit and elapsed > self.weekly_reclassify_seconds:
                    result.weekly_exhausted = True
                    self.cap_log.record_cap(
                        self.seat,
                        f"WEEKLY-EXHAUSTED (5h rolling refill passed, still out-of-credits; awaiting weekly reset): {cap_msg}",
                        detected_at=self._clock(), reset_at=None,   # weekly reset time unknown
                    )
                    self.heartbeat.beat(
                        self.name, CAPPED,
                        detail=f"weekly-exhausted (5h did not help) awaiting weekly reset: {cap_msg}"[:200],
                        iteration=i,
                    )
                    self._sleep(self.weekly_probe_seconds)          # probe hourly, not every 15 min
                elif is_credit:
                    reset_at = self._cap_start + self.credit_refill_seconds
                    self.cap_log.record_cap(self.seat, cap_msg, detected_at=self._clock(), reset_at=reset_at)
                    self.heartbeat.beat(
                        self.name, CAPPED,
                        detail=f"credits(5h auto-refill) reset_at={reset_at:.0f}: {cap_msg}"[:200],
                        iteration=i,
                    )
                    remaining = reset_at - self._clock()
                    self._sleep(min(self.cap_backoff_seconds, remaining) if remaining > 0 else self.cap_backoff_seconds)
                else:
                    reset_at = self._cap_start + self.cap_backoff_seconds
                    self.cap_log.record_cap(self.seat, cap_msg, detected_at=self._clock(), reset_at=reset_at)
                    self.heartbeat.beat(self.name, CAPPED, detail=f"cap reset_at={reset_at:.0f}: {cap_msg}"[:200], iteration=i)
                    self._sleep(self.cap_backoff_seconds)
                continue
            # A clean iteration after a cap == the seat recovered (credits back / host up).
            if self._cap_start is not None:
                self.cap_log.record_reset(self.seat, at=self._clock())
                self._cap_start = None
                result.weekly_exhausted = False
        result.stopped_reason = result.stopped_reason or "completed"
        self.heartbeat.beat(self.name, IDLE, iteration=i)
        return result
