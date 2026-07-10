"""Vendor judge exec routes through the anti-wedge chokepoint
(hardening/vendor-exec-treekill-2026-07-10, addresses D2/D1/D3).

Before: every judge backend used judge_backends._default_runner =
plain subprocess.run(timeout=...), which on timeout kills only the direct child
and leaks ssh/codex grandchildren — the nightly-wedge class, one layer down.

After: _default_runner delegates to reliability.safe_exec.run_guarded, so a
timeout tears down the whole PROCESS TREE, stdin is written-then-closed (EOF, no
codex stdin-hang), and the hard wall-clock timeout is enforced — while the
JUDGE_ERROR string contract and the happy path are unchanged.
"""
from __future__ import annotations

import sys
import time

from overmind.reliability import safe_exec
from overmind.verification.judge_backends import JUDGE_ERROR, _default_runner


# --- happy path + JUDGE_ERROR contract preserved --------------------------------

def test_success_returns_stripped_stdout():
    out = _default_runner([sys.executable, "-c", "print('VERDICT: PASS')"], "", {}, 30)
    assert out == "VERDICT: PASS"


def test_nonzero_exit_is_judge_error():
    out = _default_runner([sys.executable, "-c", "import sys; sys.exit(2)"], "", {}, 30)
    assert out.startswith(JUDGE_ERROR)
    assert "exit 2" in out


def test_spawn_failure_is_judge_error():
    out = _default_runner(["this_executable_does_not_exist_xyz"], "", {}, 5)
    assert out.startswith(JUDGE_ERROR)


# --- stdin is delivered AND closed (EOF) — no D3 stdin-hang ----------------------

def test_prompt_delivered_on_stdin_and_closed():
    # the child reads all of stdin; read() only returns because stdin got EOF.
    out = _default_runner(
        [sys.executable, "-c", "import sys; d = sys.stdin.read(); print('got', len(d))"],
        "judge this diff", {}, 15,
    )
    assert out == "got 15"


# --- timeout tears down the tree and returns promptly (does not wedge) ----------

def test_timeout_kills_tree_and_returns_fast():
    start = time.perf_counter()
    out = _default_runner([sys.executable, "-c", "import time; time.sleep(30)"], "", {}, 1)
    elapsed = time.perf_counter() - start
    assert out.startswith(JUDGE_ERROR)
    assert "TimeoutExpired" in out and "process tree killed" in out
    # returned near the 1s timeout, not the 30s sleep — the launcher did not wedge.
    assert elapsed < 15


# --- routing proof: _default_runner actually goes through run_guarded -----------

def test_default_runner_routes_through_run_guarded(monkeypatch):
    captured: dict = {}

    def _fake_run_guarded(argv, *, timeout, env=None, stdin_text=None, **kw):
        captured["argv"] = argv
        captured["timeout"] = timeout
        captured["env"] = env
        captured["stdin_text"] = stdin_text
        return safe_exec.ExecResult(0, "VERDICT: PASS", "", False, 0.01)

    # _default_runner imports run_guarded from the module at call time, so patching
    # the module attribute intercepts it.
    monkeypatch.setattr(safe_exec, "run_guarded", _fake_run_guarded)

    out = _default_runner(["claude", "-p"], "the prompt", {"CODEX_HOME": "/x"}, 180)
    assert out == "VERDICT: PASS"
    assert captured["argv"] == ["claude", "-p"]
    assert captured["stdin_text"] == "the prompt"        # prompt handed to the guard
    assert captured["timeout"] == 180.0
    # the scrubbed-env + override is passed through (token/CODEX_HOME survive)
    assert captured["env"].get("CODEX_HOME") == "/x"


def test_run_guarded_timeout_maps_to_judge_error(monkeypatch):
    def _timed_out(argv, **kw):
        return safe_exec.ExecResult(-1, "", "boom\n[timed out after 5s; process tree killed]", True, 5.0)

    monkeypatch.setattr(safe_exec, "run_guarded", _timed_out)
    out = _default_runner(["codex", "exec", "-"], "p", {}, 5)
    assert out.startswith(JUDGE_ERROR) and "TimeoutExpired" in out


# --- run_guarded stdin_text param (additive) ------------------------------------

def test_run_guarded_stdin_text_delivered():
    res = safe_exec.run_guarded(
        [sys.executable, "-c", "import sys; print('got', sys.stdin.read())"],
        timeout=15, stdin_text="abc",
    )
    assert res.ok is True
    assert "got abc" in res.stdout


def test_run_guarded_stdin_none_still_eof():
    # default (no stdin_text) -> DEVNULL -> read() returns 0 bytes, unchanged.
    res = safe_exec.run_guarded(
        [sys.executable, "-c", "import sys; print('read', len(sys.stdin.read()))"],
        timeout=15,
    )
    assert "read 0" in res.stdout
