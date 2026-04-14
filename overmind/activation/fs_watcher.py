"""Post-push / file-change watcher that polls indexed project roots.

Shrinks the feedback loop from ~24h (nightly) to minutes: when files in an
indexed project change, queue a verification task for that project
immediately. Uses filesystem polling rather than `watchdog`/`watchfiles`
to avoid adding a C-extension dependency; on indexed repos of typical
size, a 30s poll interval costs a few hundred stat() calls per tick and
is cheap enough.

This module is intentionally a thin observer — it does NOT dispatch the
verifier directly. It enqueues a `verification` task via
`TaskQueue.upsert` so the orchestrator's normal scheduling / policy
pipeline applies. If the orchestrator is not running, tasks just queue
up until the next `overmind run-once`.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from overmind.storage.models import ProjectRecord


# Directory names we never peek inside. Keeps the poll O(n) in source files.
_IGNORE_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "dist", "build", ".next", ".cache",
    "site-packages", ".tox", "target",
}
_WATCHED_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs",
                     ".html", ".css", ".json", ".yaml", ".yml", ".toml",
                     ".r", ".R", ".rmd", ".Rmd", ".sql"}


@dataclass(slots=True)
class ProjectSnapshot:
    project_id: str
    fingerprint: str
    file_count: int


def _fingerprint_project(root: Path, max_files: int = 2000) -> ProjectSnapshot | None:
    """Cheap fingerprint: hash of (rel_path, mtime_ns, size) tuples.

    Skips hidden dirs, build artefacts, and files larger than 2MB (those are
    typically generated or data files, not source we want to react to).
    """
    if not root.exists() or not root.is_dir():
        return None
    hasher = hashlib.sha256()
    count = 0
    try:
        for dirpath, dirnames, filenames in _safe_walk(root):
            dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS and not d.startswith(".")]
            for name in filenames:
                suffix = Path(name).suffix.lower()
                if suffix not in _WATCHED_SUFFIXES:
                    continue
                file_path = Path(dirpath) / name
                try:
                    stat = file_path.stat()
                except OSError:
                    continue
                if stat.st_size > 2 * 1024 * 1024:
                    continue
                rel = file_path.relative_to(root).as_posix()
                hasher.update(
                    f"{rel}|{stat.st_mtime_ns}|{stat.st_size}\n".encode("utf-8")
                )
                count += 1
                if count >= max_files:
                    break
            if count >= max_files:
                break
    except OSError:
        return None
    return ProjectSnapshot(
        project_id="",  # caller fills
        fingerprint=hasher.hexdigest()[:16],
        file_count=count,
    )


def _safe_walk(root: Path):
    import os as _os

    def _on_error(_exc: OSError) -> None:
        return None

    for dirpath, dirnames, filenames in _os.walk(
        str(root), onerror=_on_error, followlinks=False,
    ):
        yield dirpath, dirnames, filenames


class FileSystemWatcher:
    """Poll indexed projects and fire a callback when a fingerprint changes.

    Caller responsibilities:
      - Supply a `projects_fn` that returns the current indexed
        ProjectRecord list (so watcher sees adds/removes from rescans).
      - Supply a `changed_callback(project_id)` that enqueues whatever
        should happen on change — usually a verification task.
    """

    def __init__(
        self,
        projects_fn: Callable[[], Iterable[ProjectRecord]],
        changed_callback: Callable[[str], None],
        interval_seconds: float = 30.0,
    ) -> None:
        self.projects_fn = projects_fn
        self.changed_callback = changed_callback
        self.interval_seconds = interval_seconds
        self._snapshots: dict[str, str] = {}

    def tick(self) -> list[str]:
        """Single poll pass. Returns the project_ids that fired callbacks."""
        fired: list[str] = []
        seen_ids: set[str] = set()
        for project in self.projects_fn():
            seen_ids.add(project.project_id)
            snap = _fingerprint_project(Path(project.root_path))
            if snap is None:
                continue
            prior = self._snapshots.get(project.project_id)
            if prior is None:
                self._snapshots[project.project_id] = snap.fingerprint
                continue
            if prior != snap.fingerprint:
                self._snapshots[project.project_id] = snap.fingerprint
                try:
                    self.changed_callback(project.project_id)
                    fired.append(project.project_id)
                except Exception:
                    # Swallow callback errors — one bad project shouldn't stop
                    # the watcher. Caller is expected to log upstream.
                    continue
        # Drop snapshots for projects that are no longer indexed so memory
        # doesn't grow across de-indexing cycles.
        for stale in set(self._snapshots) - seen_ids:
            self._snapshots.pop(stale, None)
        return fired

    def run(self, iterations: int | None = None) -> None:
        """Blocking loop for CLI usage. Ctrl-C exits cleanly."""
        count = 0
        try:
            while iterations is None or count < iterations:
                self.tick()
                count += 1
                if iterations is not None and count >= iterations:
                    break
                time.sleep(self.interval_seconds)
        except KeyboardInterrupt:
            return
