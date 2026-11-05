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

import json
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

    def to_dict(self) -> dict:
        return {
            "loop": self.loop,
            "completed": list(self.completed),
            "state": dict(self.state),
            "updated_at": self.updated_at,
            "commit_sha": self.commit_sha,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Checkpoint":
        return cls(
            loop=str(d.get("loop", "")),
            completed=list(d.get("completed", []) or []),
            state=dict(d.get("state", {}) or {}),
            updated_at=float(d.get("updated_at", 0.0) or 0.0),
            commit_sha=str(d.get("commit_sha", "") or ""),
        )


class CheckpointStore:
    """One atomic checkpoint file per loop under ``base_dir``."""

    def __init__(
        self, base_dir: Path | str, *, clock: Callable[[], float] = time.time,
        commit_sha: str | None = None,
    ) -> None:
        # Callers resuming work against a Git checkout should supply the exact
        # commit head. A missing/legacy head then cannot satisfy this resume.
        if commit_sha is not None and not re.fullmatch(r"[0-9a-fA-F]{40}", commit_sha):
            raise ValueError("commit_sha must be a full 40-character Git SHA")
        self.base_dir = Path(base_dir)
        self._clock = clock
        self.commit_sha = commit_sha.lower() if commit_sha is not None else None

    def _path(self, loop: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in loop) or "loop"
        return self.base_dir / f"{safe}.checkpoint.json"

    def load(self, loop: str) -> Checkpoint | None:
        path = self._path(loop)
        if not path.exists():
            return None
        try:
            cp = Checkpoint.from_dict(json.loads(path.read_text(encoding="utf-8")))
            # Distinct loop names can sanitize to the same filename. Never
            # consume a different loop's completion record as our own.
            if cp.loop != loop:
                return None
            # A new revision invalidates prior completed-item evidence. Legacy
            # unbound checkpoints are deliberately not trusted by bound callers.
            if self.commit_sha is not None and cp.commit_sha != self.commit_sha:
                return None
            return cp
        except (OSError, json.JSONDecodeError, ValueError):
            return None

    def save(self, loop: str, completed: Iterable[str], state: dict | None = None) -> Checkpoint:
        cp = Checkpoint(
            loop=loop, completed=list(dict.fromkeys(completed)),  # dedup, keep order
            state=dict(state or {}), updated_at=self._clock(),
            commit_sha=self.commit_sha or "",
        )
        self._atomic_write(loop, cp.to_dict())
        return cp

    def mark_done(self, loop: str, item_id: str, *, state: dict | None = None) -> Checkpoint:
        """Record one completed item incrementally (idempotent)."""
        cp = self.load(loop) or Checkpoint(loop=loop, commit_sha=self.commit_sha or "")
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
        path = self._path(loop)
        try:
            path.unlink()
        except OSError:
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
