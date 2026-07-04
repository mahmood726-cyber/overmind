"""Tests for lightweight checkpoint/resume (reliability item 6)."""
from __future__ import annotations

from overmind.reliability.checkpoint import CheckpointStore


class _Clock:
    def __init__(self, t=100.0):
        self.t = t
    def __call__(self):
        return self.t


def test_save_and_load(tmp_path):
    store = CheckpointStore(tmp_path, clock=_Clock())
    store.save("bench", ["a", "b"], state={"phase": "arm-C"})
    cp = store.load("bench")
    assert cp is not None
    assert cp.completed == ["a", "b"]
    assert cp.state["phase"] == "arm-C"


def test_load_missing_returns_none(tmp_path):
    assert CheckpointStore(tmp_path).load("nope") is None


def test_mark_done_incremental_and_idempotent(tmp_path):
    store = CheckpointStore(tmp_path)
    store.mark_done("bench", "task1")
    store.mark_done("bench", "task2")
    store.mark_done("bench", "task1")  # idempotent
    cp = store.load("bench")
    assert cp.completed == ["task1", "task2"]


def test_remaining_is_resume_worklist(tmp_path):
    store = CheckpointStore(tmp_path)
    store.mark_done("bench", "t1")
    store.mark_done("bench", "t3")
    remaining = store.remaining("bench", ["t1", "t2", "t3", "t4"])
    assert remaining == ["t2", "t4"]


def test_remaining_all_when_no_checkpoint(tmp_path):
    store = CheckpointStore(tmp_path)
    assert store.remaining("fresh", ["a", "b"]) == ["a", "b"]


def test_is_done(tmp_path):
    store = CheckpointStore(tmp_path)
    store.mark_done("bench", "x")
    assert store.is_done("bench", "x") is True
    assert store.is_done("bench", "y") is False


def test_resume_simulation(tmp_path):
    # simulate: run 4 tasks, "crash" after 2, resume skips the done ones
    store = CheckpointStore(tmp_path)
    all_items = ["i1", "i2", "i3", "i4"]
    processed_run1 = []
    for item in store.remaining("bench", all_items):
        processed_run1.append(item)
        store.mark_done("bench", item)
        if len(processed_run1) == 2:
            break  # crash
    assert processed_run1 == ["i1", "i2"]
    # resume
    processed_run2 = []
    for item in store.remaining("bench", all_items):
        processed_run2.append(item)
        store.mark_done("bench", item)
    assert processed_run2 == ["i3", "i4"]  # only the remaining ones


def test_save_dedups(tmp_path):
    store = CheckpointStore(tmp_path)
    cp = store.save("l", ["a", "a", "b"])
    assert cp.completed == ["a", "b"]


def test_clear(tmp_path):
    store = CheckpointStore(tmp_path)
    store.mark_done("l", "a")
    store.clear("l")
    assert store.load("l") is None


def test_sanitizes_loop_name(tmp_path):
    store = CheckpointStore(tmp_path)
    store.mark_done("bench/arm C:1", "a")  # unsafe chars
    assert store.is_done("bench/arm C:1", "a") is True


def test_atomic_no_tmp_leftover(tmp_path):
    store = CheckpointStore(tmp_path)
    store.save("l", ["a"])
    assert not list(tmp_path.glob("*.tmp*"))
