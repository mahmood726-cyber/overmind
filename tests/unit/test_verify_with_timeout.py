"""Behavior tests for runner._verify_with_timeout.

Phase-4 M-2 moved _verify_with_timeout from scripts/nightly_verify.py to
overmind/nightly/runner.py. The function is the multiprocessing harness
around TruthCertEngine.verify and has three control flows: worker
returns OK, worker hangs (timeout), worker raises. Each path produces
a different CertBundle shape.

These tests fake multiprocessing.Process and multiprocessing.Queue so
they exercise the harness logic without spinning up real workers
(which would take seconds per test and depend on the engine being
fully constructable). The existing
test_select_projects_filter.test_verify_with_timeout_uses_psutil_kill_tree
checks SOURCE-CODE substrings for the psutil branch — these tests
exercise actual BEHAVIOR.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from overmind.nightly import runner
from overmind.verification.scope_lock import ScopeLock


def _fake_scope_lock() -> ScopeLock:
    return ScopeLock(
        project_id="fake-proj-abcd1234",
        project_path="C:/fake",
        risk_profile="medium",
        witness_count=1,
        test_command="python -m pytest -q",
        smoke_modules=(),
        baseline_path=None,
        expected_outcome="pass",
        source_hash="0" * 16,
        created_at="2026-05-25T00:00:00Z",
    )


def _fake_engine_and_proj():
    engine = SimpleNamespace(
        baselines_dir=Path("/tmp/baselines"),
        test_suite_witness=SimpleNamespace(timeout=120),
        build_scope_lock=lambda _proj: _fake_scope_lock(),
    )
    proj = SimpleNamespace(
        project_id="fake-proj-abcd1234",
        to_dict=lambda: {"project_id": "fake-proj-abcd1234"},
    )
    return engine, proj


class _FakeProcess:
    """multiprocessing.Process stand-in with controllable is_alive()."""

    def __init__(self, *, alive_states):
        # Iterator of bool values returned by successive is_alive() calls.
        self._alive_states = iter(alive_states)
        self._current_alive = True
        self.pid = 12345
        self.start_called = False
        self.terminate_called = False
        self.kill_called = False

    def start(self):
        self.start_called = True

    def is_alive(self):
        try:
            self._current_alive = next(self._alive_states)
        except StopIteration:
            pass
        return self._current_alive

    def terminate(self):
        self.terminate_called = True
        self._current_alive = False

    def kill(self):
        self.kill_called = True
        self._current_alive = False

    def join(self, timeout=None):
        self._current_alive = False


class _FakeQueue:
    """multiprocessing.Queue stand-in. .get_nowait() returns from a pre-seeded
    list or raises if empty."""

    def __init__(self, *, items=None):
        self._items = list(items or [])

    def get_nowait(self):
        if not self._items:
            import queue
            raise queue.Empty()
        return self._items.pop(0)

    def close(self):
        pass

    def join_thread(self):
        pass


@pytest.fixture
def patch_mp(monkeypatch):
    """Patch multiprocessing.Queue and Process inside _verify_with_timeout's
    inline import. Returns a configurator the test calls with (process, queue)."""
    import multiprocessing

    def _install(process, queue):
        monkeypatch.setattr(multiprocessing, "Queue", lambda: queue)
        monkeypatch.setattr(multiprocessing, "Process", lambda **kw: process)

    return _install


def test_returns_certbundle_on_worker_success(patch_mp, monkeypatch):
    """Happy path: worker completes; queue yields ("ok", bundle_dict);
    _verify_with_timeout reconstructs and returns a CertBundle."""
    engine, proj = _fake_engine_and_proj()

    bundle_dict = {
        "project_id": "fake-proj-abcd1234",
        "scope_lock": {
            "project_id": "fake-proj-abcd1234",
            "project_path": "C:/fake",
            "risk_profile": "medium",
            "witness_count": 1,
            "test_command": "python -m pytest -q",
            "smoke_modules": [],
            "baseline_path": None,
            "expected_outcome": "pass",
            "source_hash": "0" * 16,
            "created_at": "2026-05-25T00:00:00Z",
        },
        "witness_results": [{
            "witness_type": "test_suite", "verdict": "PASS",
            "exit_code": 0, "stdout": "ok", "stderr": "", "elapsed": 1.0,
        }],
        "verdict": "PASS",
        "arbitration_reason": "single witness PASS",
        "timestamp": "2026-05-25T00:00:01Z",
        "bundle_hash": "abcd1234deadbeef",
    }
    # is_alive returns False on first poll → loop exits clean.
    proc = _FakeProcess(alive_states=[False])
    q = _FakeQueue(items=[("ok", bundle_dict)])
    patch_mp(proc, q)
    # Avoid the time.sleep(2) the poll loop does — the loop also exits on
    # the first iteration when is_alive=False, so this isn't strictly needed
    # but pins fast-path semantics.
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    result = runner._verify_with_timeout(engine, proj, timeout=10)

    assert proc.start_called is True
    assert proc.terminate_called is False, "happy path should not terminate"
    assert result.project_id == "fake-proj-abcd1234"
    assert result.verdict == "PASS"
    assert len(result.witness_results) == 1
    assert result.witness_results[0].verdict == "PASS"


def test_returns_synthetic_fail_on_worker_hang(patch_mp, monkeypatch):
    """Timeout path: worker stays alive past the deadline; harness emits a
    synthetic FAIL CertBundle with the 'Hard timeout' arbitration reason."""
    engine, proj = _fake_engine_and_proj()

    # is_alive always True → loop exits via deadline, terminate path runs.
    proc = _FakeProcess(alive_states=[True] * 100)
    q = _FakeQueue()  # never read
    patch_mp(proc, q)
    # Skip the 2s poll sleep so the test finishes in <1s.
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    result = runner._verify_with_timeout(engine, proj, timeout=0.01)

    assert proc.terminate_called is True
    assert result.verdict == "FAIL"
    assert "Hard timeout" in result.arbitration_reason
    assert result.witness_results[0].stderr.startswith("Project hung")


def test_returns_synthetic_fail_on_worker_error(patch_mp, monkeypatch):
    """Error path: worker completed but queue yields ("error", message);
    harness emits a synthetic FAIL CertBundle wrapping the message."""
    engine, proj = _fake_engine_and_proj()

    proc = _FakeProcess(alive_states=[False])
    q = _FakeQueue(items=[("error", "Worker exploded: ImportError")])
    patch_mp(proc, q)
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    result = runner._verify_with_timeout(engine, proj, timeout=10)

    assert result.verdict == "FAIL"
    assert "Worker exploded" in result.arbitration_reason
    assert "Worker error" in result.witness_results[0].stderr


def test_returns_synthetic_fail_on_empty_queue(patch_mp, monkeypatch):
    """No-result path: worker died without putting anything on the queue;
    harness emits a synthetic FAIL with 'no result' reason."""
    engine, proj = _fake_engine_and_proj()

    proc = _FakeProcess(alive_states=[False])
    q = _FakeQueue()  # empty — get_nowait raises queue.Empty
    patch_mp(proc, q)
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    result = runner._verify_with_timeout(engine, proj, timeout=10)

    assert result.verdict == "FAIL"
    assert "no result" in result.arbitration_reason.lower()
    assert result.witness_results[0].stderr == "Worker returned no result"
