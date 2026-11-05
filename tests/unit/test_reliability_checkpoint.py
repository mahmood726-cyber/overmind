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
    assert store._legacy_path("run/one") == store._legacy_path("run_one")
    assert store._path("run/one") != store._path("run_one")
    store.mark_done("run/one", "first")
    store.mark_done("run_one", "second")
    # Two distinct loops now coexist; neither can overwrite the other.
    assert store.is_done("run/one", "first") is True
    assert store.is_done("run/one", "second") is False
    assert store.is_done("run_one", "second") is True
    assert store.is_done("run_one", "first") is False


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
        raw_before = store._path("run").read_text(encoding="utf-8")
        assert store.load("run") is None, payload
        assert not store.is_done("run", "done"), payload
        assert store.remaining("run", ["done", "other"]) == ["done", "other"], payload
        # Reading an invalid checkpoint must not silently mutate it.
        assert store._path("run").read_text(encoding="utf-8") == raw_before


def test_legacy_checkpoint_read_then_incremental_migration(tmp_path):
    import json

    store = CheckpointStore(tmp_path, clock=_Clock())
    legacy = store._legacy_path("run/one")
    legacy.write_text(
        json.dumps({"loop": "run/one", "completed": ["old"], "state": {"phase": "one"}, "updated_at": 1}),
        encoding="utf-8",
    )
    assert store.is_done("run/one", "old")
    assert not store.is_done("run_one", "old")  # shared old filename, mismatched identity
    store.mark_done("run/one", "new")
    assert store._path("run/one").exists()
    assert store.load("run/one").completed == ["old", "new"]
    assert store.load("run/one").state == {"phase": "one"}
    # Migration does not corrupt or overwrite the original source bytes.
    assert json.loads(legacy.read_text(encoding="utf-8"))["completed"] == ["old"]


def test_clear_never_deletes_other_loops_legacy_file(tmp_path):
    import json

    store = CheckpointStore(tmp_path)
    legacy = store._legacy_path("run/one")
    legacy.write_text(
        json.dumps({"loop": "run/one", "completed": ["old"]}), encoding="utf-8"
    )
    store.mark_done("run_one", "new")
    store.clear("run_one")
    assert legacy.exists()
    assert store.is_done("run/one", "old")
    assert not store.is_done("run_one", "new")
    store.clear("run/one")
    assert not legacy.exists()


def test_corrupt_modern_checkpoint_does_not_resurrect_legacy_success(tmp_path):
    import json

    store = CheckpointStore(tmp_path)
    store._legacy_path("run").write_text(
        json.dumps({"loop": "run", "completed": ["stale"]}), encoding="utf-8"
    )
    store._path("run").write_text(
        '{"loop":"run","completed":{"stale":true}}', encoding="utf-8"
    )
    assert store.load("run") is None
    assert store.remaining("run", ["stale"]) == ["stale"]


def test_hashed_checkpoint_path_is_portable_and_bounded(tmp_path):
    store = CheckpointStore(tmp_path)
    loop = "trial/" + ("x" * 300) + "/β"
    path = store._path(loop)
    assert len(path.name.encode("utf-8")) < 200
    assert all(ord(char) < 128 for char in path.name)
    assert path == CheckpointStore(tmp_path)._path(loop)
    store.mark_done(loop, "done")
    assert CheckpointStore(tmp_path).is_done(loop, "done")


def test_plan_change_at_same_head_invalidates_completed_items(tmp_path):
    import hashlib

    head = "a" * 40
    old_plan = hashlib.sha256(b"python -m pytest tests/unit").hexdigest()
    changed_plan = hashlib.sha256(b"python -m pytest tests/integration").hexdigest()
    original = CheckpointStore(tmp_path, commit_sha=head, plan_sha=old_plan)
    original.mark_done("check", "tests")
    # Exact-head AND exact-plan restarts may reuse already completed checks.
    assert CheckpointStore(tmp_path, commit_sha=head, plan_sha=old_plan).is_done(
        "check", "tests"
    )
    # Changed commands at the SAME Git head cannot reuse the old completion.
    changed = CheckpointStore(tmp_path, commit_sha=head, plan_sha=changed_plan)
    assert changed.load("check") is None
    assert not changed.is_done("check", "tests")
    assert changed.remaining("check", ["tests", "build"]) == ["tests", "build"]
    changed.mark_done("check", "build")
    restarted = CheckpointStore(
        tmp_path, commit_sha=head, plan_sha=changed_plan
    ).load("check")
    assert restarted is not None
    assert restarted.plan_sha == changed_plan
    assert restarted.completed == ["build"]  # stale test result stays excluded


def test_plan_bound_resume_refuses_legacy_unbound_completion(tmp_path):
    import hashlib

    head = "b" * 40
    CheckpointStore(tmp_path, commit_sha=head).mark_done("check", "stale")
    bounded = CheckpointStore(
        tmp_path, commit_sha=head,
        plan_sha=hashlib.sha256(b"new plan").hexdigest(),
    )
    assert bounded.load("check") is None
    assert bounded.remaining("check", ["stale"]) == ["stale"]
    # Legacy callers remain able to read their old unbound records.
    assert CheckpointStore(tmp_path, commit_sha=head).is_done("check", "stale")


def test_plan_digest_requires_full_sha256_and_normalizes_case(tmp_path):
    import hashlib
    import pytest

    for bad in ("", "g" * 64, "a" * 63, "a" * 65):
        with pytest.raises(ValueError, match="plan_sha"):
            CheckpointStore(tmp_path, plan_sha=bad)
    digest = hashlib.sha256(b"synthetic command plan").hexdigest()
    CheckpointStore(tmp_path, plan_sha=digest.upper()).mark_done("check", "yes")
    resumed = CheckpointStore(tmp_path, plan_sha=digest).load("check")
    assert resumed is not None
    assert resumed.plan_sha == digest
    assert resumed.completed == ["yes"]


def test_malformed_persisted_plan_digest_never_yields_completion(tmp_path):
    import json

    store = CheckpointStore(tmp_path)
    for bad in (42, "not-a-sha", [], "a" * 63):
        record = {"loop": "check", "completed": ["looks_done"], "plan_sha": bad}
        raw = json.dumps(record)
        store._path("check").write_text(raw, encoding="utf-8")
        assert store.load("check") is None
        assert not store.is_done("check", "looks_done")
        assert store.remaining("check", ["looks_done"]) == ["looks_done"]
        # The invalid source record must not be modified to manufacture PASS.
        assert store._path("check").read_text(encoding="utf-8") == raw


def test_unbound_reader_refuses_head_bound_checkpoint(tmp_path):
    """Missing local head identity must not trust completion from another checkout."""
    head = "a" * 40
    CheckpointStore(tmp_path, commit_sha=head).mark_done("run", "task")
    unbound = CheckpointStore(tmp_path)
    assert unbound.load("run") is None
    assert not unbound.is_done("run", "task")
    assert unbound.remaining("run", ["task"]) == ["task"]
    assert CheckpointStore(tmp_path, commit_sha=head).is_done("run", "task")


def test_unbound_reader_refuses_plan_bound_checkpoint(tmp_path):
    """Omitting a plan digest must not mean 'accept any saved plan'."""
    import hashlib

    plan = hashlib.sha256(b"synthetic checks v1").hexdigest()
    CheckpointStore(tmp_path, plan_sha=plan).mark_done("run", "task")
    unbound = CheckpointStore(tmp_path)
    assert unbound.load("run") is None
    assert not unbound.is_done("run", "task")
    assert CheckpointStore(tmp_path, plan_sha=plan).is_done("run", "task")


def test_partially_bound_reader_refuses_missing_context(tmp_path):
    import hashlib

    head = "b" * 40
    plan = hashlib.sha256(b"synthetic checks v2").hexdigest()
    CheckpointStore(tmp_path, commit_sha=head, plan_sha=plan).mark_done("run", "task")
    for reader in (
        CheckpointStore(tmp_path, commit_sha=head),
        CheckpointStore(tmp_path, plan_sha=plan),
        CheckpointStore(tmp_path),
    ):
        assert reader.load("run") is None
        assert reader.remaining("run", ["task"]) == ["task"]
    assert CheckpointStore(tmp_path, commit_sha=head, plan_sha=plan).is_done("run", "task")


def test_legacy_unbound_checkpoint_still_resumes_unbound_reader(tmp_path):
    """Unbound records retain their historical unbound-consumer semantics."""
    CheckpointStore(tmp_path).mark_done("old", "task")
    assert CheckpointStore(tmp_path).is_done("old", "task")


def test_interleaved_checkpoint_saves_use_distinct_atomic_temps(tmp_path, monkeypatch):
    """Two threads in one PID must never share a temp file before os.replace."""
    import os

    store = CheckpointStore(tmp_path)
    real_replace = os.replace
    sources = []
    interleaved = False

    def overlap(first, target):
        nonlocal interleaved
        sources.append(str(first))
        if not interleaved:
            interleaved = True
            # Deterministically simulate a second same-process writer while
            # the first is waiting to replace its own temporary file.
            store.save("run", ["inner"])
        return real_replace(first, target)

    monkeypatch.setattr(os, "replace", overlap)
    store.save("run", ["outer"])
    assert len(sources) == 2
    assert len(set(sources)) == 2  # PID-only temp names used to alias.
    assert store.load("run").completed == ["outer"]
    assert not list(tmp_path.glob(".checkpoint-*.tmp"))


def test_failed_atomic_rename_removes_temp_and_preserves_last_good_result(
    tmp_path, monkeypatch
):
    """An interrupted save must not leak temp files or certify new progress."""
    import os

    store = CheckpointStore(tmp_path)
    store.mark_done("run", "durable")
    before = store._path("run").read_bytes()

    def fail_replace(_src, _dst):
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    store.mark_done("run", "not-durable")
    assert store._path("run").read_bytes() == before
    assert store.load("run").completed == ["durable"]
    assert store.is_done("run", "not-durable") is False
    assert not list(tmp_path.glob(".checkpoint-*.tmp"))


def test_failed_first_save_returns_no_unrecorded_completion(tmp_path, monkeypatch):
    """A failed replace cannot make save() claim an item was checkpointed."""
    import os

    store = CheckpointStore(tmp_path)
    def fail_replace(_src, _dst):
        raise OSError("synthetic write failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    returned = store.save("run", ["not-recorded"], state={"phase": "unwritten"})
    assert returned.completed == []
    assert returned.state == {}
    assert store.load("run") is None
    assert not store.is_done("run", "not-recorded")
    assert not list(tmp_path.glob(".checkpoint-*.tmp"))


def test_failed_mark_done_returns_prior_recorded_evidence(tmp_path, monkeypatch):
    """Failed incremental save must not attest to the new task or state."""
    import os

    store = CheckpointStore(tmp_path)
    store.mark_done("run", "previous", state={"phase": "recorded"})
    prior_bytes = store._path("run").read_bytes()

    def fail_replace(_src, _dst):
        raise OSError("synthetic interrupted rename")

    monkeypatch.setattr(os, "replace", fail_replace)
    returned = store.mark_done("run", "not-recorded", state={"phase": "unwritten"})
    assert returned.completed == ["previous"]
    assert returned.state == {"phase": "recorded"}
    assert store._path("run").read_bytes() == prior_bytes
    assert store.remaining("run", ["previous", "not-recorded"]) == ["not-recorded"]
    assert not list(tmp_path.glob(".checkpoint-*.tmp"))


def test_failed_bound_write_does_not_adopt_other_revision(tmp_path, monkeypatch):
    """Even fallback evidence must match the caller's exact commit/plan."""
    import os

    old = CheckpointStore(tmp_path, commit_sha="a" * 40, plan_sha="b" * 64)
    old.mark_done("run", "previous-head")
    current = CheckpointStore(tmp_path, commit_sha="c" * 40, plan_sha="d" * 64)

    def fail_replace(_src, _dst):
        raise OSError("synthetic unavailable destination")

    monkeypatch.setattr(os, "replace", fail_replace)
    returned = current.mark_done("run", "new-head")
    assert returned.completed == []
    assert returned.commit_sha == "c" * 40
    assert returned.plan_sha == "d" * 64
    assert current.load("run") is None
    assert current.remaining("run", ["previous-head", "new-head"]) == [
        "previous-head", "new-head"
    ]
    assert not list(tmp_path.glob(".checkpoint-*.tmp"))
