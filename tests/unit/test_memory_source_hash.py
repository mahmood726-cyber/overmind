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


# ── Retraction propagation over derived_from (audit B2) ─────────────


def test_derived_from_round_trips_through_db(tmp_path):
    store, db = _store(tmp_path)
    try:
        store.save(MemoryRecord(
            memory_id="b", memory_type="project_learning", scope="p",
            title="t", content="c", derived_from=["a"],
        ))
        got = db.get_memory("b")
        assert got is not None
        assert got.derived_from == ["a"]
    finally:
        db.close()


def _seed_chain(store, tmp_path):
    source = tmp_path / "src.txt"
    source.write_text("original", encoding="utf-8")
    h = file_source_hash(source)
    store.save_batch([
        MemoryRecord(memory_id="A", memory_type="project_learning", scope="p",
                     title="A", content="A", source_path=str(source), source_hash=h),
        MemoryRecord(memory_id="B", memory_type="project_learning", scope="p",
                     title="B", content="B", derived_from=["A"]),
        MemoryRecord(memory_id="C", memory_type="project_learning", scope="p",
                     title="C", content="C", derived_from=["B"]),
        MemoryRecord(memory_id="D", memory_type="project_learning", scope="p",
                     title="D", content="D"),
    ])
    return source


def test_flat_invalidation_leaves_dependents_standing(tmp_path):
    store, db = _store(tmp_path)
    try:
        source = _seed_chain(store, tmp_path)
        source.write_text("CHANGED", encoding="utf-8")
        store.invalidate_stale()
        active = {m.memory_id for m in store.list_all(status="active", limit=100)}
        # Only A expired; B and C (derived from A) wrongly remain active.
        assert "A" not in active
        assert "B" in active and "C" in active and "D" in active
    finally:
        db.close()


def test_propagation_invalidates_transitive_dependents(tmp_path):
    store, db = _store(tmp_path)
    try:
        source = _seed_chain(store, tmp_path)
        source.write_text("CHANGED", encoding="utf-8")
        out = store.invalidate_stale_with_propagation()
        active = {m.memory_id for m in store.list_all(status="active", limit=100)}
        # A (stale) + B + C (transitively derived) all expired; D preserved.
        assert active == {"D"}
        assert out["direct"] == 1
        assert out["propagated"] == 2
    finally:
        db.close()


def test_propagate_retraction_does_not_touch_independent(tmp_path):
    store, db = _store(tmp_path)
    try:
        _seed_chain(store, tmp_path)
        out = store.propagate_retraction(["A"])
        active = {m.memory_id for m in store.list_all(status="active", limit=100)}
        assert "D" in active
        assert set(out["invalidated"]) == {"B", "C"}
    finally:
        db.close()


def test_recall_filters_mutated_sources_and_transitive_unknowns(tmp_path):
    store, db = _store(tmp_path)
    try:
        source = _seed_chain(store, tmp_path)
        assert {m.memory_id for m in store.recall_for_project("p")} == {"A", "B", "C", "D"}
        store.save_batch([
            MemoryRecord(
                memory_id="unknown", memory_type="project_learning", scope="p",
                title="Synthetic unknown", content="Synthetic unknown parent",
                derived_from=["unregistered"],
            ),
            MemoryRecord(
                memory_id="partial", memory_type="project_learning", scope="p",
                title="Synthetic partial", content="Synthetic incomplete source",
                source_path=str(source),
            ),
            MemoryRecord(
                memory_id="x", memory_type="project_learning", scope="p",
                title="Synthetic cycle x", content="Synthetic cycle x",
                derived_from=["y"],
            ),
            MemoryRecord(
                memory_id="y", memory_type="project_learning", scope="p",
                title="Synthetic cycle y", content="Synthetic cycle y",
                derived_from=["x"],
            ),
            MemoryRecord(
                memory_id="cross", memory_type="project_learning", scope="p",
                title="Synthetic cross", content="Synthetic cross scope",
                derived_from=["other"],
            ),
            MemoryRecord(
                memory_id="other", memory_type="project_learning", scope="q",
                title="Synthetic other", content="Synthetic other project",
            ),
        ])
        source.write_text("CHANGED", encoding="utf-8")
        assert {m.memory_id for m in store.recall_for_project("p", limit=30)} == {"D"}
        assert store.search("Synthetic", scope="p", limit=30) == []
        assert {m.memory_id for m in store.recall_for_project("q")} == {"other"}
        assert db.get_memory("A").status == "active"  # read does not falsify audit
        assert db.get_memory("B").status == "active"
    finally:
        db.close()


def test_context_injector_read_does_not_leak_stale_or_other_project(tmp_path):
    from overmind.activation.context_injector import ContextInjector
    from overmind.storage.models import ProjectRecord

    store, db = _store(tmp_path)
    try:
        source = _seed_chain(store, tmp_path)
        db.upsert_project(ProjectRecord(
            project_id="p", name="Synthetic project", root_path=str(tmp_path)
        ))
        store.save(MemoryRecord(
            memory_id="other-secret", memory_type="heuristic", scope="other-project",
            title="PRIVATE_OTHER_PROJECT", content="Synthetic private memory",
        ))
        source.write_text("CHANGED", encoding="utf-8")
        injected = ContextInjector(db).build_context(project_path=str(tmp_path))
        assert "[project_learning] D: D" in injected
        for forbidden in ("[project_learning] A:", "[project_learning] B:",
                          "[project_learning] C:", "PRIVATE_OTHER_PROJECT"):
            assert forbidden not in injected
    finally:
        db.close()


def test_stale_high_ranked_memories_do_not_starve_valid_recall(monkeypatch, tmp_path):
    """Paging must find lower-ranked live evidence beyond a stale first page."""
    from overmind.memory import embeddings

    monkeypatch.setattr("overmind.storage.db.embeddings.embed", lambda _: [1.0, 0.0])
    store, db = _store(tmp_path)
    try:
        changed = tmp_path / "changed.txt"
        changed.write_text("now", encoding="utf-8")
        for i in range(40):
            store.save(MemoryRecord(
                memory_id=f"stale-{i:02}", memory_type="project_learning",
                scope="project-a", title="Synthetic raretoken",
                content=f"Synthetic raretoken stale evidence {i}",
                relevance=1.0, source_path=str(changed),
                source_hash="0000000000000000",
                embedding=[1.0, 0.0],
            ))
        store.save(MemoryRecord(
            memory_id="live", memory_type="project_learning",
            scope="project-a", title="Synthetic raretoken",
            content="Synthetic raretoken live evidence", relevance=0.1,
            embedding=[0.0, 1.0],
        ))
        store.save(MemoryRecord(
            memory_id="other", memory_type="project_learning",
            scope="project-b", title="Synthetic raretoken",
            content="Synthetic raretoken other-project", embedding=[1.0, 0.0],
        ))
        assert [m.memory_id for m in store.recall_for_project("project-a", limit=1)] == ["live"]
        assert [m.memory_id for m in store.search("raretoken", scope="project-a", limit=1)] == ["live"]
        assert [m.memory_id for m in store.hybrid_search("unmatchable", scope="project-a", limit=1)] == ["live"]
        assert [m.memory_id for m in store.recall_for_project("project-b", limit=1)] == ["other"]
        # Administrative inspection must retain original stale-source records.
        assert db.get_memory("stale-00").status == "active"
    finally:
        db.close()
