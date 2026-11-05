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


def test_resume_is_tied_to_exact_commit_head(tmp_path):
    head_a = "a" * 40
    head_b = "b" * 40
    original = CheckpointStore(tmp_path, commit_sha=head_a)
    original.mark_done("run", "a", state={"phase": "done"})
    assert CheckpointStore(tmp_path, commit_sha=head_a).remaining("run", ["a", "b"]) == ["b"]
    changed = CheckpointStore(tmp_path, commit_sha=head_b)
    assert changed.load("run") is None
    assert changed.is_done("run", "a") is False
    assert changed.remaining("run", ["a", "b"]) == ["a", "b"]
    changed.mark_done("run", "b")
    restarted = CheckpointStore(tmp_path, commit_sha=head_b).load("run")
    assert restarted is not None
    assert restarted.commit_sha == head_b
    assert restarted.completed == ["b"]  # old 'a' must not leak into new head


def test_bound_resume_rejects_legacy_checkpoint_without_head(tmp_path):
    CheckpointStore(tmp_path).mark_done("run", "finished-on-unknown-revision")
    bound = CheckpointStore(tmp_path, commit_sha="a" * 40)
    assert bound.load("run") is None
    assert bound.remaining("run", ["finished-on-unknown-revision"]) == [
        "finished-on-unknown-revision"
    ]


def test_sanitized_loop_collision_does_not_reuse_completion(tmp_path):
    store = CheckpointStore(tmp_path)
    store.mark_done("run/one", "finished")
    # Previously this path collision returned the first loop's completed set.
    assert store._path("run/one") == store._path("run_one")
    assert store.load("run_one") is None
    assert store.is_done("run_one", "finished") is False
    assert store.remaining("run_one", ["finished"]) == ["finished"]


def test_commit_head_requires_full_sha(tmp_path):
    import pytest

    for bad in ("", "abc", "z" * 40, "a" * 39):
        with pytest.raises(ValueError, match="full 40-character"):
            CheckpointStore(tmp_path, commit_sha=bad)


def test_commit_sha_survives_restart_and_case_normalization(tmp_path):
    uppercase = "AB" * 20
    store = CheckpointStore(tmp_path, commit_sha=uppercase)
    store.save("loop", ["complete"])
    resumed = CheckpointStore(tmp_path, commit_sha=uppercase.lower())
    assert resumed.is_done("loop", "complete")
    assert resumed.load("loop").commit_sha == uppercase.lower()


def test_legacy_valid_checkpoint_json_still_resumes(tmp_path):
    import json

    store = CheckpointStore(tmp_path)
    store._path("run").write_text(
        json.dumps({"loop": "run", "completed": ["done"], "state": {}, "updated_at": 1.0}),
        encoding="utf-8",
    )
    assert store.is_done("run", "done")
    assert store.remaining("run", ["done", "other"]) == ["other"]


def test_malformed_checkpoint_fails_closed(tmp_path):
    import json
    import pytest

    # Valid JSON can still be structurally corrupt or claim completion from
    # unsupported types. Never promote these values to verified work.
    invalid = [
        [],
        {"loop": "run", "completed": {"done": True}},
        {"loop": "run", "completed": "done"},
        {"loop": "run", "completed": ["done", 1]},
        {"loop": "run", "completed": ["done"], "state": ["broken"]},
        {"loop": "run", "completed": ["done"], "updated_at": "yesterday"},
        {"loop": "run", "completed": ["done"], "updated_at": float("nan")},
        {"loop": "run", "completed": ["done"], "commit_sha": "bad-head"},
        {"loop": 123, "completed": ["done"]},
        {"completed": ["done"]},
    ]
    for payload in invalid:
        store = CheckpointStore(tmp_path)
        store._path("run").write_text(json.dumps(payload), encoding="utf-8")
        assert store.load("run") is None, payload
        assert not store.is_done("run", "done"), payload
        assert store.remaining("run", ["done", "other"]) == ["done", "other"], payload
        # Reading an invalid checkpoint must not silently mutate it.
        assert json.loads(store._path("run").read_text(encoding="utf-8")) == payload
