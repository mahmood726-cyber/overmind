"""Lightweight per-loop checkpoint/resume (reliability — item 6).

For long runs — especially the §3 benchmark — a killed process should RESUME
rather than restart from zero. This is the minimal state-file pattern (the same
``.progress_<date>.json`` idea already used across the stack), NOT an execution
graph engine: one atomic JSON file per loop recording the completed item ids +
arbitrary state, so ``remaining()`` skips what is already done on restart.

Atomic write (temp + ``os.replace``); best-effort — a checkpoint failure never
crashes the loop it protects. A failed write must not return an unrecorded
completion as though it had been saved.
"""
from __future__ import annotations

import errno
import hashlib
import json
import math
import os
import re
import tempfile
import time
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable


@dataclass(slots=True)
class Checkpoint:
    loop: str
    completed: list[str] = field(default_factory=list)
    state: dict = field(default_factory=dict)
    updated_at: float = 0.0
    commit_sha: str = ""  # exact source head; empty marks legacy/unbound data
    plan_sha: str = ""  # SHA-256 of exact verification plan; empty is unbound

    def to_dict(self) -> dict:
        return {
            "loop": self.loop,
            "completed": list(self.completed),
            "state": dict(self.state),
            "updated_at": self.updated_at,
            "commit_sha": self.commit_sha,
            "plan_sha": self.plan_sha,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Checkpoint":
        # Do not coerce malformed JSON into completion evidence. In particular,
        # list(dict) treats dict keys as completed items, and list(str) treats
        # individual characters as completed items. These are not valid records.
        if not isinstance(d, dict) or not isinstance(d.get("loop"), str):
            raise ValueError("checkpoint must contain a string loop identity")
        completed = d.get("completed", [])
        if not isinstance(completed, list) or any(not isinstance(x, str) or not x for x in completed):
            raise ValueError("checkpoint completed must be a list of item ids")
        state = d.get("state", {})
        if not isinstance(state, dict):
            raise ValueError("checkpoint state must be a mapping")
        updated_at = d.get("updated_at", 0.0)
        if (isinstance(updated_at, bool) or not isinstance(updated_at, (int, float))
                or not math.isfinite(updated_at)):
            raise ValueError("checkpoint timestamp must be finite and numeric")
        commit_sha = d.get("commit_sha", "")
        if not isinstance(commit_sha, str) or (commit_sha and not re.fullmatch(r"[0-9a-fA-F]{40}", commit_sha)):
            raise ValueError("checkpoint commit_sha must be empty or a full Git SHA")
        plan_sha = d.get("plan_sha", "")
        if not isinstance(plan_sha, str) or (plan_sha and not re.fullmatch(r"[0-9a-fA-F]{64}", plan_sha)):
            raise ValueError("checkpoint plan_sha must be empty or a full SHA-256 digest")
        return cls(
            loop=d["loop"], completed=list(completed), state=dict(state),
            updated_at=float(updated_at), commit_sha=commit_sha.lower(),
            plan_sha=plan_sha.lower(),
        )


class CheckpointStore:
    """One atomic checkpoint file per loop under ``base_dir``."""

    def __init__(
        self, base_dir: Path | str, *, clock: Callable[[], float] = time.time,
        commit_sha: str | None = None, plan_sha: str | None = None,
    ) -> None:
        # Callers resuming work against a Git checkout should supply the exact
        # commit head. A missing/legacy head then cannot satisfy this resume.
        if commit_sha is not None and not re.fullmatch(r"[0-9a-fA-F]{40}", commit_sha):
            raise ValueError("commit_sha must be a full 40-character Git SHA")
        # A caller-supplied canonical plan digest prevents reuse when an item
        # id refers to different checks after a verification-plan change.
        if plan_sha is not None and not re.fullmatch(r"[0-9a-fA-F]{64}", plan_sha):
            raise ValueError("plan_sha must be a full 64-character SHA-256 digest")
        self.base_dir = Path(base_dir)
        self._clock = clock
        self.commit_sha = commit_sha.lower() if commit_sha is not None else None
        self.plan_sha = plan_sha.lower() if plan_sha is not None else None

    def _legacy_path(self, loop: str) -> Path:
        # Original sanitized filename, retained only for read-only migration.
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in loop) or "loop"
        return self.base_dir / f"{safe}.checkpoint.json"

    def _path(self, loop: str) -> Path:
        # Sanitizing alone aliases e.g. "run/one" and "run_one". The digest
        # preserves exact loop identity even across Windows/Linux filesystems,
        # and the shortened readable prefix avoids platform filename limits.
        safe = "".join(
            c if c.isascii() and (c.isalnum() or c in "-_.") else "_"
            for c in loop
        )[:64] or "loop"
        digest = hashlib.sha256(loop.encode("utf-8")).hexdigest()
        return self.base_dir / f"{safe}.{digest}.checkpoint.json"

    def _temp_prefix(self, loop: str) -> str:
        """Stable per-loop prefix for identifying recoverable temp files."""
        return f".checkpoint-{hashlib.sha256(loop.encode('utf-8')).hexdigest()}-"

    @contextmanager
    def _write_lock(self, loop: str):
        """Serialize same-loop updates across processes, including crash recovery.

        Keep the lock file after release: deleting it can split concurrent
        processes across distinct inodes and defeat advisory locking.
        Unsupported platforms or lock contention fail closed for writes.
        """
        self.base_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self._path(loop).with_suffix(".lock")
        with lock_path.open("a+b") as handle:
            if os.name == "nt":
                import msvcrt

                # msvcrt.locking locks a byte range at the current position.
                # Ensure the byte exists; another opener writing the same zero
                # during initialization is harmless.
                if handle.seek(0, os.SEEK_END) == 0:
                    handle.write(bytes([0]))
                    handle.flush()

                def acquire():
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)

                def release():
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            elif os.name == "posix":
                import fcntl

                def acquire():
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                def release():
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            else:
                raise OSError("checkpoint file locking unsupported on this OS")

            deadline = time.monotonic() + 5.0
            while True:
                try:
                    acquire()
                    break
                except OSError as exc:
                    if exc.errno not in (errno.EACCES, errno.EAGAIN):
                        raise
                    if time.monotonic() >= deadline:
                        raise TimeoutError("checkpoint write lock unavailable") from exc
                    time.sleep(0.02)
            try:
                # A hard-killed writer cannot execute _atomic_write's finally
                # cleanup. Only after acquiring this loop's exclusive lock may
                # we remove its abandoned temp files. Never touch a different
                # loop's possibly live temp files, or old unattributed temps.
                for orphan in self.base_dir.glob(f"{self._temp_prefix(loop)}*.tmp"):
                    try:
                        orphan.unlink()
                    except OSError:
                        pass  # harmless debris; no completion evidence comes from temps
                yield
            finally:
                release()

    def load(self, loop: str) -> Checkpoint | None:
        primary = self._path(loop)
        try:
            # A present but invalid modern record must NOT fall back to old
            # evidence. Only a missing modern record permits legacy reading.
            path = primary if primary.exists() else self._legacy_path(loop)
            if not path.exists():
                return None
            cp = Checkpoint.from_dict(json.loads(path.read_text(encoding="utf-8")))
            if cp.loop != loop:
                return None
            # A new revision invalidates prior completed-item evidence. Legacy
            # unbound checkpoints are deliberately not trusted by bound callers.
            # Binding must match in BOTH directions: an unbound caller has no
            # evidence that a stored revision-bound result belongs to its
            # checkout, just as a bound caller cannot trust legacy evidence.
            if cp.commit_sha != (self.commit_sha or ""):
                return None
            # Likewise, an omitted plan identity must never accept completion
            # evidence recorded under a specific verification plan.
            if cp.plan_sha != (self.plan_sha or ""):
                return None
            return cp
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return None

    def _last_recorded(self, loop: str) -> Checkpoint:
        """Return existing readable evidence, never the rejected write payload."""
        return self.load(loop) or Checkpoint(
            loop=loop, commit_sha=self.commit_sha or "", plan_sha=self.plan_sha or "",
        )

    def save(self, loop: str, completed: Iterable[str], state: dict | None = None) -> Checkpoint:
        # Strings and mappings are iterable, but their characters/keys are
        # not completed task evidence. Never publish them as completed IDs.
        if isinstance(completed, (str, bytes, Mapping)):
            return self._last_recorded(loop)
        try:
            with self._write_lock(loop):
                items = list(completed)
                if any(not isinstance(item, str) or not item for item in items):
                    return self._last_recorded(loop)
                cp = Checkpoint(
                    loop=loop, completed=list(dict.fromkeys(items)),  # dedup, keep order
                    state=dict(state or {}), updated_at=self._clock(),
                    commit_sha=self.commit_sha or "", plan_sha=self.plan_sha or "",
                )
                if not self._atomic_write(loop, cp.to_dict()):
                    return self._last_recorded(loop)
                return cp
        except (OSError, TypeError, ValueError):
            # Invalid iterables and state mappings must not crash recovery.
            return self._last_recorded(loop)

    def mark_done(self, loop: str, item_id: str, *, state: dict | None = None) -> Checkpoint:
        """Record one completed item incrementally (idempotent)."""
        if not isinstance(item_id, str) or not item_id:
            return self._last_recorded(loop)
        try:
            # The read/modify/write sequence must be one critical section.
            # Atomic replacement alone does not protect concurrent increments.
            with self._write_lock(loop):
                cp = self.load(loop) or Checkpoint(
                    loop=loop, commit_sha=self.commit_sha or "", plan_sha=self.plan_sha or "",
                )
                if item_id not in cp.completed:
                    cp.completed.append(item_id)
                if state is not None:
                    cp.state.update(state)
                cp.updated_at = self._clock()
                if not self._atomic_write(loop, cp.to_dict()):
                    return self._last_recorded(loop)
                return cp
        except (OSError, TypeError, ValueError):
            return self._last_recorded(loop)

    def is_done(self, loop: str, item_id: str) -> bool:
        cp = self.load(loop)
        return bool(cp and item_id in cp.completed)

    def remaining(self, loop: str, all_items: Iterable[str]) -> list[str]:
        """Items not yet completed — the resume worklist after a kill."""
        cp = self.load(loop)
        done = set(cp.completed) if cp else set()
        return [i for i in all_items if i not in done]

    def clear(self, loop: str) -> None:
        try:
            with self._write_lock(loop):
                try:
                    self._path(loop).unlink()
                except OSError:
                    pass
                # Legacy filenames may alias distinct loops. Never remove an
                # unrelated loop's historical evidence during a clear.
                legacy = self._legacy_path(loop)
                try:
                    if legacy.exists():
                        cp = Checkpoint.from_dict(json.loads(legacy.read_text(encoding="utf-8")))
                        if cp.loop == loop:
                            legacy.unlink()
                except (OSError, json.JSONDecodeError, TypeError, ValueError):
                    pass
        except OSError:
            pass

    def _atomic_write(self, loop: str, payload: dict) -> bool:
        # A PID-only temporary filename is shared by threads in one process.
        # Interleaved saves could replace each other's bytes or leave a missing
        # source for os.replace(), silently discarding one completion update.
        tmp: Path | None = None
        try:
            # Serialize strictly and validate the exact on-disk representation
            # before replacing the last known-good checkpoint. JSON permits
            # NaN by default; an unreadable file must never be acknowledged as
            # completed, nor should an unserializable state crash recovery.
            encoded = json.dumps(payload, allow_nan=False)
            validated = Checkpoint.from_dict(json.loads(encoded))
            if validated.loop != loop:
                return False
            self.base_dir.mkdir(parents=True, exist_ok=True)
            path = self._path(loop)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.base_dir,
                prefix=self._temp_prefix(loop), suffix=".tmp", delete=False,
            ) as handle:
                tmp = Path(handle.name)
                handle.write(encoded)
                # Flush Python buffers, then ask the OS to persist the file
                # contents BEFORE publishing a new checkpoint. If sync fails,
                # leave the previous checkpoint intact and do not acknowledge
                # the new completion. The directory rename is not separately
                # fsynced, so this is not a full power-loss durability claim.
                handle.flush()
                os.fsync(handle.fileno())
            # NamedTemporaryFile is closed before replace for Windows support.
            os.replace(tmp, path)
            return True
        except (OSError, TypeError, ValueError, OverflowError, RecursionError):
            return False  # no completion acknowledgement for invalid/failed writes
        finally:
            # Also remove abandoned temps after a failed replace/write. Never
            # remove another writer's file: temp names are independently unique.
            if tmp is not None:
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass
