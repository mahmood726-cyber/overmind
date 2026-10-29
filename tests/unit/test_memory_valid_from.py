"""Synthetic temporal-validity regressions for Overmind memory recall.

A future-effective fact is stored for audit but must not be returned as
currently usable evidence by project, FTS or semantic recall.
"""
from __future__ import annotations

from overmind.memory.store import MemoryStore
from overmind.storage.db import StateDatabase
from overmind.storage.models import MemoryRecord


def test_future_valid_memory_is_hidden_until_effective(monkeypatch, tmp_path):
    clock = {"now": "2026-10-29T12:00:00+00:00"}
    monkeypatch.setattr("overmind.storage.db.utc_now", lambda: clock["now"])
    monkeypatch.setattr("overmind.storage.db.embeddings.embed", lambda _: [1.0, 0.0])

    db = StateDatabase(tmp_path / "state.db")
    store = MemoryStore(db, tmp_path / "checkpoints", tmp_path / "logs")
    try:
        def memory(mid, scope, start=None, end=None):
            return MemoryRecord(
                memory_id=mid,
                memory_type="project_learning",
                scope=scope,
                title="Synthetic epoch evidence",
                content=f"Synthetic evidence for {mid}",
                valid_from=start,
                valid_until=end,
                embedding=[1.0, 0.0],
            )

        store.save_batch([
            memory("current", "project-a", "2026-10-28T12:00:00+00:00"),
            memory("future", "project-a", "2026-11-01T12:00:00+00:00"),
            memory("expired", "project-a", end="2026-10-28T12:00:00+00:00"),
            memory("other", "project-b"),
        ])

        def observed():
            return (
                {m.memory_id for m in store.recall_for_project("project-a")},
                {m.memory_id for m in store.search("Synthetic", scope="project-a")},
                {m.memory_id for m, _ in db.semantic_search_memories(
                    "Synthetic", scope="project-a"
                )},
                {m.memory_id for m in store.hybrid_search(
                    "Synthetic", scope="project-a"
                )},
            )

        assert store.get("future") is not None  # available for audit only
        assert observed() == ({"current"},) * 4

        clock["now"] = "2026-11-02T12:00:00+00:00"
        assert observed() == ({"current", "future"},) * 4
        assert {m.memory_id for m in store.recall_for_project("project-b")} == {
            "other"
        }
    finally:
        db.close()
