"""Advisory per-repo lane lock (isolation hardening 2026-07-12).

``WorktreeManager.needs_isolation`` decides whether a lane should get its own
worktree by checking a set of active roots — but that check is NOT atomic: two
lanes that start together can both observe the shared root as free, both skip
isolation, and both mutate the same checkout, so one lane's commits land on the
other's branch (observed failure #7). This module is the atomic backstop: an
``O_EXCL`` lockfile in the repo root that only ONE lane can hold, with a clear
error naming the current holder for the loser.

It is deliberately simple and dependency-free:
  * Atomic acquire via ``os.open(..., O_CREAT | O_EXCL)`` — the OS guarantees
    exactly one winner even under a race.
  * The lockfile records holder / pid / host / timestamp so the error is
    actionable ("held by lane-B (pid 1234) since …").
  * A stale-lock TTL breaks a lock whose holder died without releasing (a crashed
    lane / PC restart) — logged loudly, never silent, so a genuinely-live holder
    is never stolen from within the TTL.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

LOCK_FILENAME = ".overmind-lane.lock"
# A lock older than this with no refresh is assumed abandoned (crashed lane / PC
# restart) and may be broken. Generous so a legitimately long lane is never
# stolen from; a live lane should refresh() well within it.
DEFAULT_STALE_AFTER_SECONDS: float = 3600.0


class RepoLockedError(RuntimeError):
    """Raised when another live lane already holds the repo lock."""


@dataclass(slots=True)
class LockInfo:
    holder: str
    pid: int
    host: str
    acquired_at: float

    def to_json(self) -> str:
        return json.dumps({
            "holder": self.holder, "pid": self.pid,
            "host": self.host, "acquired_at": self.acquired_at,
        })

    @classmethod
    def from_path(cls, path: Path) -> "LockInfo | None":
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            return cls(holder=str(d.get("holder", "?")), pid=int(d.get("pid", -1)),
                       host=str(d.get("host", "?")), acquired_at=float(d.get("acquired_at", 0.0)))
        except (OSError, ValueError, TypeError):
            return None


class RepoLock:
    """Atomic advisory lock over a repo root. Use as a context manager::

        with RepoLock(repo_root, holder="lane-A"):
            ...  # exclusive mutation of the checkout

    The SECOND concurrent lane raises :class:`RepoLockedError` with the current
    holder — a clear error instead of a silent shared-tree collision.
    """

    def __init__(
        self,
        repo_root: str | Path,
        *,
        holder: str,
        stale_after: float = DEFAULT_STALE_AFTER_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.holder = holder
        self.stale_after = stale_after
        self.clock = clock
        self._path = self.repo_root / LOCK_FILENAME
        self._held = False

    def _write_lockfile(self) -> None:
        info = LockInfo(self.holder, os.getpid(), socket.gethostname(), self.clock())
        fd = os.open(str(self._path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            os.write(fd, info.to_json().encode("utf-8"))
        finally:
            os.close(fd)

    def acquire(self) -> "RepoLock":
        try:
            self._write_lockfile()
            self._held = True
            return self
        except FileExistsError:
            pass
        # Lock exists — is it stale (dead holder) or a live lane?
        existing = LockInfo.from_path(self._path)
        age = (self.clock() - existing.acquired_at) if existing else None
        if existing is not None and age is not None and age <= self.stale_after:
            raise RepoLockedError(
                f"repo {self.repo_root} is locked by {existing.holder} "
                f"(pid {existing.pid} on {existing.host}) since "
                f"{age:.0f}s ago — refusing to share the checkout"
            )
        # Stale/unreadable lock: break it loudly, then take it.
        logger.warning(
            "breaking stale repo lock on %s (held by %s, age %s > %.0fs TTL)",
            self.repo_root,
            existing.holder if existing else "?",
            f"{age:.0f}s" if age is not None else "unknown",
            self.stale_after,
        )
        try:
            self._path.unlink()
        except OSError:
            pass
        self._write_lockfile()   # may still raise RepoLockedError on a re-race — correct
        self._held = True
        return self

    def refresh(self) -> None:
        """Re-stamp the lock's timestamp so a long-running holder is not judged
        stale. A live lane should call this periodically (heartbeat)."""
        if not self._held:
            return
        info = LockInfo(self.holder, os.getpid(), socket.gethostname(), self.clock())
        try:
            self._path.write_text(info.to_json(), encoding="utf-8")
        except OSError:
            pass

    def release(self) -> None:
        if not self._held:
            return
        # Only remove a lockfile we actually own (guard against removing a lock a
        # stale-breaker handed to someone else).
        existing = LockInfo.from_path(self._path)
        if existing is not None and existing.holder == self.holder and existing.pid == os.getpid():
            try:
                self._path.unlink()
            except OSError:
                pass
        self._held = False

    def __enter__(self) -> "RepoLock":
        return self.acquire()

    def __exit__(self, *exc) -> None:
        self.release()
