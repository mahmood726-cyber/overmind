from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from overmind.storage.db import StateDatabase
from overmind.storage.models import InsightRecord, MemoryRecord


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

    def decay_all(self, factor: float = 0.95) -> int:
        return self.db.decay_memories(factor)

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

    def stats(self) -> dict[str, int]:
        return self.db.memory_stats()

    def save_insights(self, insights: list[InsightRecord]) -> None:
        for insight in insights:
            self.db.add_insight(insight)

    def write_checkpoint(self, name: str, payload: dict[str, Any]) -> None:
        self.db.write_checkpoint(name, payload)
        checkpoint_path = self.checkpoints_dir / f"{name}.json"
        checkpoint_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
