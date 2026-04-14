"""Tests for memory source-hash grounding (the 'memory != evidence' enforcer)."""
from __future__ import annotations

from pathlib import Path

from overmind.memory.dream_engine import DreamEngine, FAILURE_CLUSTER_MIN_PROJECTS
from overmind.memory.store import MemoryStore, file_source_hash
from overmind.storage.db import StateDatabase
from overmind.storage.models import MemoryRecord


def _store(tmp_path: Path) -> tuple[MemoryStore, StateDatabase]:
    db = StateDatabase(tmp_path / "state.db")
    store = MemoryStore(db, tmp_path / "checkpoints", tmp_path / "logs")
    return store, db


def test_file_source_hash_stable_for_same_content(tmp_path):
    p = tmp_path / "f.txt"
    p.write_text("hello", encoding="utf-8")
    h1 = file_source_hash(p)
    h2 = file_source_hash(p)
    assert h1 is not None
    assert h1 == h2


def test_file_source_hash_changes_when_content_changes(tmp_path):
    p = tmp_path / "f.txt"
    p.write_text("hello", encoding="utf-8")
    h1 = file_source_hash(p)
    p.write_text("world", encoding="utf-8")
    h2 = file_source_hash(p)
    assert h1 != h2


def test_memory_without_source_is_never_stale(tmp_path):
    store, db = _store(tmp_path)
    try:
        mem = MemoryRecord(
            memory_id="m1", memory_type="runner_learning", scope="r1",
            title="t", content="c",
        )
        assert store.is_stale(mem) is False
    finally:
        db.close()


def test_memory_with_unchanged_source_is_not_stale(tmp_path):
    store, db = _store(tmp_path)
    try:
        source = tmp_path / "rule.txt"
        source.write_text("never run git push --force", encoding="utf-8")
        h = file_source_hash(source)
        mem = MemoryRecord(
            memory_id="m2", memory_type="heuristic", scope="global",
            title="t", content="c",
            source_path=str(source), source_hash=h,
        )
        store.save(mem)
        assert store.is_stale(mem) is False
    finally:
        db.close()


def test_memory_with_changed_source_is_stale(tmp_path):
    store, db = _store(tmp_path)
    try:
        source = tmp_path / "rule.txt"
        source.write_text("original", encoding="utf-8")
        h = file_source_hash(source)
        mem = MemoryRecord(
            memory_id="m3", memory_type="heuristic", scope="global",
            title="t", content="c",
            source_path=str(source), source_hash=h,
        )
        store.save(mem)

        source.write_text("overwritten", encoding="utf-8")
        assert store.is_stale(mem) is True
    finally:
        db.close()


def test_memory_with_deleted_source_is_stale(tmp_path):
    store, db = _store(tmp_path)
    try:
        source = tmp_path / "rule.txt"
        source.write_text("gone soon", encoding="utf-8")
        h = file_source_hash(source)
        mem = MemoryRecord(
            memory_id="m4", memory_type="heuristic", scope="global",
            title="t", content="c",
            source_path=str(source), source_hash=h,
        )
        store.save(mem)
        source.unlink()
        assert store.is_stale(mem) is True
    finally:
        db.close()


def test_invalidate_stale_expires_stale_memories(tmp_path):
    store, db = _store(tmp_path)
    try:
        source = tmp_path / "rule.txt"
        source.write_text("v1", encoding="utf-8")
        h = file_source_hash(source)
        mem = MemoryRecord(
            memory_id="m5", memory_type="heuristic", scope="global",
            title="t", content="c",
            source_path=str(source), source_hash=h,
        )
        store.save(mem)
        source.write_text("v2", encoding="utf-8")

        count = store.invalidate_stale()
        assert count == 1
        reloaded = store.get("m5")
        assert reloaded is not None
        assert reloaded.status == "expired"
        assert reloaded.valid_until is not None
    finally:
        db.close()


def test_dream_engine_emits_failure_cluster_when_threshold_met(tmp_path):
    store, db = _store(tmp_path)
    try:
        for i in range(FAILURE_CLUSTER_MIN_PROJECTS):
            store.save(MemoryRecord(
                memory_id=f"bf-{i}",
                memory_type="bundle_failure",
                scope=f"proj-{i}",
                title=f"proj-{i}: missing_baseline",
                content="tier-3 project has no baseline",
                tags=["nightly", "bundle_failure", "failure_class:missing_baseline"],
            ))

        engine = DreamEngine(db)
        emitted = engine._phase_failure_clusters()

        assert len(emitted) == 1
        cluster = emitted[0]
        assert cluster.memory_type == "heuristic"
        assert cluster.scope == "portfolio"
        assert "missing_baseline" in cluster.title
        assert "failure_class:missing_baseline" in cluster.tags
    finally:
        db.close()


def test_dream_engine_skips_cluster_below_threshold(tmp_path):
    store, db = _store(tmp_path)
    try:
        store.save(MemoryRecord(
            memory_id="bf-only",
            memory_type="bundle_failure",
            scope="proj-solo",
            title="proj-solo: timeout",
            content="one-off",
            tags=["bundle_failure", "failure_class:timeout"],
        ))
        engine = DreamEngine(db)
        emitted = engine._phase_failure_clusters()
        assert emitted == []
    finally:
        db.close()
