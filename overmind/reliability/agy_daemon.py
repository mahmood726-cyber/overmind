"""agy (Antigravity) stale-daemon reaper (reliability, #5 — 2026-07-12).

The agy driver's ``language_server.exe`` daemon caches trajectories and, when
several stale copies linger (a crashed CLI, a PC restart), agy returns 0-step
conversations / cold-start 90s discovery timeouts and looks DEAD even though its
quota pool is live (cross-vendor 2026-07-11: agy was recovered by killing 2 stale
``language_server.exe`` daemons + a fresh launch).

This reaps daemons whose age exceeds a threshold BEFORE an agy probe, so a fresh
launch is clean. It is:
  * **injectable** — ``list_procs`` / ``kill`` / ``clock`` are parameters, so the
    selection logic is unit-tested without touching real processes;
  * **opt-in** — nothing calls it automatically; a caller reaps deliberately
    before an agy liveness probe. Auto-killing a live daemon is exactly the
    false-positive we avoid, so age-gating is mandatory.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)

AGY_DAEMON_NAME = "language_server.exe"
# Only reap a daemon older than this. A fresh, healthy daemon (seconds old) is
# never touched; only long-lingering stale copies are candidates.
DEFAULT_MIN_AGE_SECONDS: float = 300.0

Proc = dict  # {"pid": int, "name": str, "create_time": float}


def find_stale_daemons(
    procs: list[Proc], *, now: float, min_age: float = DEFAULT_MIN_AGE_SECONDS,
    name: str = AGY_DAEMON_NAME,
) -> list[Proc]:
    """Return the agy-daemon processes older than ``min_age`` (age-gated so a live
    daemon is never selected)."""
    out = []
    for p in procs:
        if str(p.get("name", "")).lower() != name.lower():
            continue
        ct = p.get("create_time")
        if ct is None:
            continue
        if (now - float(ct)) >= min_age:
            out.append(p)
    return out


def reap_stale_daemons(
    *,
    list_procs: Callable[[], list[Proc]] | None = None,
    kill: Callable[[int], bool] | None = None,
    now: float | None = None,
    min_age: float = DEFAULT_MIN_AGE_SECONDS,
) -> list[int]:
    """Reap stale agy daemons; return the PIDs actually killed. Age-gated: a fresh
    daemon (< ``min_age``) is left alone. Logs each kill."""
    now = time.time() if now is None else now
    list_procs = list_procs or _default_list_procs
    kill = kill or _default_kill
    stale = find_stale_daemons(list_procs(), now=now, min_age=min_age)
    reaped: list[int] = []
    for p in stale:
        pid = int(p["pid"])
        if kill(pid):
            reaped.append(pid)
            logger.warning("reaped stale agy daemon pid=%s (age %.0fs)",
                           pid, now - float(p["create_time"]))
    return reaped


def _default_list_procs() -> list[Proc]:  # pragma: no cover - real-process path
    """Enumerate language_server.exe processes via psutil if present, else []."""
    try:
        import psutil  # type: ignore
    except ImportError:
        logger.info("psutil not installed — agy daemon reaper is a no-op")
        return []
    out: list[Proc] = []
    for proc in psutil.process_iter(["pid", "name", "create_time"]):
        try:
            info = proc.info
            if str(info.get("name", "")).lower() == AGY_DAEMON_NAME.lower():
                out.append({"pid": info["pid"], "name": info["name"],
                            "create_time": info["create_time"]})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return out


def _default_kill(pid: int) -> bool:  # pragma: no cover - real-process path
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                           capture_output=True, timeout=5, check=True)
        else:
            import os
            import signal
            os.kill(pid, signal.SIGKILL)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
