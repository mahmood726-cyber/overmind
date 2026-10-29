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

def test_timezone_offset_windows_and_invalid_time_fail_closed(monkeypatch, tmp_path):
    """SQLite must compare instants, not ISO strings with different UTC offsets."""
    clock = {"now": "2026-10-29T06:00:00+00:00"}
    monkeypatch.setattr("overmind.storage.db.utc_now", lambda: clock["now"])
    monkeypatch.setattr("overmind.storage.db.embeddings.embed", lambda _: [1.0, 0.0])

    db = StateDatabase(tmp_path / "offset-state.db")
    store = MemoryStore(db, tmp_path / "checkpoints", tmp_path / "logs")
    try:
        def synthetic(mid, scope="project-a", start=None, end=None):
            return MemoryRecord(
                memory_id=mid, memory_type="project_learning", scope=scope,
                title="Synthetic offset evidence", content="Synthetic boundary fact",
                valid_from=start, valid_until=end, embedding=[1.0, 0.0],
            )

        store.save_batch([
            synthetic("current-offset", start="2026-10-29T07:00:00+02:00"),
            synthetic("future-offset", start="2026-10-29T03:00:00-04:00"),
            synthetic("active-until-offset", end="2026-10-29T03:00:00-04:00"),
            synthetic("expired-until-offset", end="2026-10-29T07:00:00+02:00"),
            synthetic("invalid-from", start="not-an-ISO-date"),
            synthetic("invalid-until", end="not-an-ISO-date"),
            synthetic("impossible-calendar-from", start="2026-02-31T00:00:00+00:00"),
            synthetic("impossible-calendar-until", end="2026-11-31T00:00:00+00:00"),
            synthetic("one-microsecond-future", start="2026-10-29T06:00:00.000001+00:00"),
            synthetic("one-microsecond-until", end="2026-10-29T06:00:00.000001+00:00"),
            synthetic("unsupported-nanosecond-start", start="2026-10-29T06:00:00.000000001+00:00"),
            synthetic("unsupported-nanosecond-end", end="2026-11-29T06:00:00.000000001+00:00"),
            synthetic("other-project", scope="project-b"),
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

        # At 06:00Z, 07:00+02 is 05:00Z (active), whereas 03:00-04 is
        # 07:00Z (future). Malformed timestamps and impossible calendar dates
        # must never be treated as live, even when SQLite normalizes the date.
        expected = {"current-offset", "active-until-offset", "one-microsecond-until"}
        assert observed() == (expected,) * 4
        clock["now"] = "2026-10-29T08:00:00+00:00"
        expected = {"current-offset", "future-offset", "one-microsecond-future"}
        assert observed() == (expected,) * 4
        assert {m.memory_id for m in store.recall_for_project("project-b")} == {
            "other-project"
        }
    finally:
        db.close()


def test_expiry_transition_uses_utc_instant_and_refuses_corrupt_boundaries(
    monkeypatch, tmp_path
):
    """A sweep must not expire future-offset facts or preserve elapsed ones."""
    monkeypatch.setattr(
        "overmind.storage.db.utc_now", lambda: "2026-10-29T06:00:00+00:00"
    )
    db = StateDatabase(tmp_path / "expiry-transition.db")
    cases = {
        "future-offset": ("2026-10-29T03:00:00-04:00", "active"),
        "elapsed-offset": ("2026-10-29T07:00:00+02:00", "expired"),
        "future-microsecond": ("2026-10-29T06:00:00.000001+00:00", "active"),
        "elapsed-microsecond": ("2026-10-29T05:59:59.999999+00:00", "expired"),
        "invalid-calendar": ("2026-11-31T00:00:00+00:00", "expired"),
        "unsupported-nanoseconds": (
            "2026-11-01T00:00:00.000000001+00:00", "expired"
        ),
        "no-expiry": (None, "active"),
    }
    try:
        for mid, (end, _expected_status) in cases.items():
            db.upsert_memory(
                MemoryRecord(
                    memory_id=mid,
                    memory_type="project_learning",
                    scope="synthetic-project",
                    title="Synthetic expiry evidence",
                    content=f"Invented expiry fact for {mid}",
                    valid_until=end,
                )
            )
        assert db.expire_memories() == 4
        for mid, (_end, expected_status) in cases.items():
            actual = db.get_memory(mid)
            assert actual is not None
            assert actual.status == expected_status, mid
        # Idempotent: already-expired records do not change a second time.
        assert db.expire_memories() == 0
    finally:
        db.close()
