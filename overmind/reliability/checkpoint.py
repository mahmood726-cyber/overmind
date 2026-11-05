"""Lightweight per-loop checkpoint/resume (reliability — item 6).

For long runs — especially the §3 benchmark — a killed process should RESUME
rather than restart from zero. This is the minimal state-file pattern (the same
``.progress_<date>.json`` idea already used across the stack), NOT an execution
graph engine: one atomic JSON file per loop recording the completed item ids +
arbitrary state, so ``remaining()`` skips what is already done on restart.

Atomic write (temp + ``os.replace``); best-effort — a checkpoint failure never
crashes the loop it protects.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
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
        if not isinstance(completed, list) or any(not isinstance(x, str) for x in completed):
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
            if self.commit_sha is not None and cp.commit_sha != self.commit_sha:
                return None
            # A bound caller cannot trust a different or unbound plan at the
            # same commit, even if its item ids happen to match.
            if self.plan_sha is not None and cp.plan_sha != self.plan_sha:
                return None
            return cp
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return None

    def save(self, loop: str, completed: Iterable[str], state: dict | None = None) -> Checkpoint:
        cp = Checkpoint(
            loop=loop, completed=list(dict.fromkeys(completed)),  # dedup, keep order
            state=dict(state or {}), updated_at=self._clock(),
            commit_sha=self.commit_sha or "", plan_sha=self.plan_sha or "",
        )
        self._atomic_write(loop, cp.to_dict())
        return cp

    def mark_done(self, loop: str, item_id: str, *, state: dict | None = None) -> Checkpoint:
        """Record one completed item incrementally (idempotent)."""
        cp = self.load(loop) or Checkpoint(
            loop=loop, commit_sha=self.commit_sha or "", plan_sha=self.plan_sha or "",
        )
        if item_id not in cp.completed:
            cp.completed.append(item_id)
        if state is not None:
            cp.state.update(state)
        cp.updated_at = self._clock()
        self._atomic_write(loop, cp.to_dict())
        return cp

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
            self._path(loop).unlink()
        except OSError:
            pass
        # A legacy filename may be shared by another loop identity; do not
        # delete another loop's historical completion evidence on clear().
        legacy = self._legacy_path(loop)
        try:
            if legacy.exists():
                cp = Checkpoint.from_dict(json.loads(legacy.read_text(encoding="utf-8")))
                if cp.loop == loop:
                    legacy.unlink()
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    def _atomic_write(self, loop: str, payload: dict) -> None:
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            path = self._path(loop)
            tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            os.replace(tmp, path)
        except OSError:
            pass  # best-effort; never crash the protected loop
