"""Tests for anti-wedge safe_exec (reliability item 4): guarded subprocess
(timeout + tree-kill + stdin=NUL) and the ReDoS screen."""
from __future__ import annotations

import sys

import pytest

from overmind.reliability.safe_exec import (
    compile_guarded,
    looks_catastrophic,
    run_guarded,
)


# --- run_guarded ----------------------------------------------------------------

def test_run_guarded_success():
    res = run_guarded([sys.executable, "-c", "print('hello')"], timeout=30)
    assert res.ok is True
    assert "hello" in res.stdout
    assert res.timed_out is False


def test_run_guarded_nonzero_exit():
    res = run_guarded([sys.executable, "-c", "import sys; sys.exit(3)"], timeout=30)
    assert res.returncode == 3
    assert res.ok is False


def test_run_guarded_times_out_and_kills():
    # a process that would hang forever must be killed and reported timed_out
    res = run_guarded([sys.executable, "-c", "import time; time.sleep(30)"], timeout=1)
    assert res.timed_out is True
    assert res.returncode == -1
    assert "timed out" in res.stderr


def test_run_guarded_stdin_is_nul():
    # reading stdin returns EOF immediately (DEVNULL) instead of blocking forever
    res = run_guarded(
        [sys.executable, "-c", "import sys; data=sys.stdin.read(); print('read', len(data))"],
        timeout=10,
    )
    assert res.timed_out is False
    assert "read 0" in res.stdout


def test_run_guarded_bad_executable():
    res = run_guarded(["this_executable_does_not_exist_xyz"], timeout=5)
    assert res.returncode == -1
    assert "failed to start" in res.stderr


def test_run_guarded_accepts_string_command():
    res = run_guarded(f'"{sys.executable}" -c "print(42)"', timeout=30)
    assert "42" in res.stdout


# --- ReDoS screen ---------------------------------------------------------------

@pytest.mark.parametrize("pat", ["(a+)+", "(a*)*", "(.+)+", "([a-z]+)*", "(\\d+){2,}", "(\\w+\\s*)+"])
def test_looks_catastrophic_flags_nested(pat):
    assert looks_catastrophic(pat) is True


@pytest.mark.parametrize("pat", ["a+", "[abc]+", "(abc)+", "\\d{1,80}", "foo|bar", "(ab)+c+", "[\\w\\s]{1,50}"])
def test_looks_catastrophic_allows_safe(pat):
    assert looks_catastrophic(pat) is False


def test_compile_guarded_refuses_catastrophic():
    with pytest.raises(ValueError):
        compile_guarded("(a+)+")


def test_compile_guarded_compiles_safe():
    rx = compile_guarded(r"\d{1,80}")
    assert rx.match("12345") is not None


def test_run_guarded_surviving_grandchild_does_not_hang_harness(monkeypatch):
    # A grandchild that survives tree-kill keeps the inherited stdout pipe open.
    # Closing the pipes while communicate() reader threads hold them blocks until
    # that grandchild exits (A1). The timed run must return promptly instead.
    import time
    import overmind.reliability.safe_exec as se

    monkeypatch.setattr(se, "kill_process_tree", lambda proc: proc.kill())
    parent = (
        "import subprocess, sys, time\n"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(25)'])\n"
        "time.sleep(60)\n"
    )
    t0 = time.perf_counter()
    res = run_guarded([sys.executable, "-c", parent], timeout=1)
    elapsed = time.perf_counter() - t0
    assert res.timed_out is True
    assert elapsed < 15, f"harness hung {elapsed:.1f}s on surviving grandchild"
