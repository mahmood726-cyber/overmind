from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from overmind.storage.db import StateDatabase
from overmind.storage.models import InsightRecord, MemoryRecord, utc_now


def file_source_hash(path: str | Path) -> str | None:
    """SHA-256 hex prefix for a file, used to ground memory records to sources."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    return hashlib.sha256(data).hexdigest()[:16]


class MemoryStore:
    def __init__(self, db: StateDatabase, checkpoints_dir: Path, logs_dir: Path) -> None:
        self.db = db
        self.checkpoints_dir = checkpoints_dir
        self.logs_dir = logs_dir
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def save(self, memory: MemoryRecord) -> None:
        self.db.upsert_memory(memory)

    def save_batch(self, memories: list[MemoryRecord]) -> None:
        for memory in memories:
            self.db.upsert_memory(memory)

    def get(self, memory_id: str) -> MemoryRecord | None:
        return self.db.get_memory(memory_id)

    def search(
        self, query: str, scope: str | None = None, memory_type: str | None = None, limit: int = 10
    ) -> list[MemoryRecord]:
        return self.db.search_memories(query, scope=scope, memory_type=memory_type, limit=limit)

    def recall_for_project(self, project_id: str, limit: int = 5) -> list[MemoryRecord]:
        return self.db.list_memories(scope=project_id, limit=limit)

    def recall_for_runner(self, runner_id: str, limit: int = 5) -> list[MemoryRecord]:
        return self.db.list_memories(scope=runner_id, memory_type="runner_learning", limit=limit)

    def recall_heuristics(self, task_type: str, limit: int = 5) -> list[MemoryRecord]:
        return self.db.search_memories(task_type, memory_type="heuristic", limit=limit)

    # Per-type decay rates. Feedback memories encode user preferences and
    # should age very slowly; bundle_failure / regression memories couple to
    # state and age fast so the dream cluster analysis doesn't re-surface
    # yesterday's problem after it's been fixed.
    DEFAULT_DECAY_RATES: dict[str, float] = {
        "feedback": 0.99,
        "user": 0.99,
        "reference": 0.98,
        "heuristic": 0.97,
        "runner_learning": 0.96,
        "project": 0.92,
        "regression": 0.90,
        "bundle_failure": 0.85,
    }

    def decay_all(
        self,
        factor: float = 0.95,
        *,
        per_type: dict[str, float] | None = None,
    ) -> int:
        """Decay relevance scores. Uses DEFAULT_DECAY_RATES when no override."""
        rates = per_type if per_type is not None else self.DEFAULT_DECAY_RATES
        return self.db.decay_memories(factor, per_type=rates)

    def archive_stale(self, threshold: float = 0.1) -> int:
        return self.db.archive_stale_memories(threshold)

    def update_relevance(self, memory_id: str, boost: float) -> None:
        memory = self.db.get_memory(memory_id)
        if not memory:
            return
        memory.relevance = round(min(1.0, memory.relevance + boost), 4)
        self.db.upsert_memory(memory)

    def forget(self, memory_id: str) -> None:
        self.db.delete_memory(memory_id)

    def list_all(self, status: str = "active", limit: int = 50) -> list[MemoryRecord]:
        return self.db.list_memories(status=status, limit=limit)

    def hybrid_search(
        self, query: str, scope: str | None = None, memory_type: str | None = None, limit: int = 10,
        semantic_fallback_threshold: int = 3,
    ) -> list[MemoryRecord]:
        """Search using FTS5 first; if fewer than threshold results, augment with semantic search.

        Deduplicates by memory_id across both result sets.
        """
        fts_results = self.search(query, scope=scope, memory_type=memory_type, limit=limit)

        if len(fts_results) >= semantic_fallback_threshold:
            return fts_results

        semantic_results = self.db.semantic_search_memories(
            query, scope=scope, memory_type=memory_type, limit=limit,
        )
        seen_ids = {m.memory_id for m in fts_results}
        merged = list(fts_results)
        for mem, _score in semantic_results:
            if mem.memory_id not in seen_ids:
                merged.append(mem)
                seen_ids.add(mem.memory_id)
            if len(merged) >= limit:
                break
        return merged

    def supersede(self, old_memory_id: str, new_memory: MemoryRecord) -> bool:
        """Close an existing memory (set valid_until) and save a new one that replaces it.

        Returns True if old memory was found and superseded.
        """
        old = self.db.get_memory(old_memory_id)
        if old is None:
            return False
        now = utc_now()
        old.valid_until = now
        old.status = "expired"
        old.updated_at = now
        self.db.upsert_memory(old)
        if new_memory.valid_from is None:
            new_memory.valid_from = now
        if old.memory_id not in new_memory.linked_memories:
            new_memory.linked_memories.append(old.memory_id)
        self.db.upsert_memory(new_memory)
        return True

    def expire_old(self) -> int:
        """Expire active memories that have passed their valid_until."""
        return self.db.expire_memories()

    def stats(self) -> dict[str, int]:
        return self.db.memory_stats()

    def is_stale(self, memory: MemoryRecord) -> bool:
        """Return True if the memory references a source whose current hash
        differs from the hash captured at extraction time. Implements the
        "memory != evidence" rule from CLAUDE.md — a memory whose source file
        was overwritten is no longer authoritative.

        Memories without a `source_path`/`source_hash` are not considered
        stale (they weren't source-grounded to begin with).
        """
        if not memory.source_path or not memory.source_hash:
            return False
        current = file_source_hash(memory.source_path)
        if current is None:
            return True  # source file gone = stale
        return current != memory.source_hash

    def invalidate_stale(self) -> int:
        """Mark source-grounded memories whose source changed as 'expired'.

        Returns the count of memories invalidated. Safe to call repeatedly —
        already-expired memories are untouched.
        """
        count = 0
        now = utc_now()
        for memory in self.list_all(status="active", limit=10_000):
            if self.is_stale(memory):
                memory.status = "expired"
                memory.valid_until = now
                memory.updated_at = now
                self.db.upsert_memory(memory)
                count += 1
        return count

    def save_insights(self, insights: list[InsightRecord]) -> None:
        for insight in insights:
            self.db.add_insight(insight)

    def write_checkpoint(self, name: str, payload: dict[str, Any]) -> int:
        checkpoint_id = self.db.write_checkpoint(name, payload)
        checkpoint_path = self.checkpoints_dir / f"{name}.json"
        checkpoint_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return checkpoint_id
