"""Tests for individual pluggable judge backends (P2-12 / design 1 & 2).

Uses injected runners/http so no CLI is spawned and no quota is burned.
"""
from __future__ import annotations

import json
from pathlib import Path

from overmind.verification.judge_backends import (
    AgyBackend,
    ClaudeCodeBackend,
    CodexBackend,
    LocalModelBackend,
    JUDGE_ERROR,
)


def _capturing_runner(captured: dict, response: str):
    def run(argv, stdin_text, env_overrides, timeout):
        captured["argv"] = argv
        captured["stdin"] = stdin_text
        captured["env"] = env_overrides
        return response
    return run


def test_claude_backend_pipes_prompt_on_stdin():
    cap: dict = {}
    backend = ClaudeCodeBackend(runner=_capturing_runner(cap, "VERDICT: PASS"))
    assert backend.query("judge this") == "VERDICT: PASS"
    assert cap["stdin"] == "judge this"
    assert cap["argv"][0].lower().startswith("claude") or "claude" in cap["argv"][0].lower()


def test_claude_backend_passes_oauth_token_not_api_key():
    # subscription OAuth path: CLAUDE_CODE_OAUTH_TOKEN is passed as env override
    cap: dict = {}
    backend = ClaudeCodeBackend(oauth_token="sk-ant-oat01-EXAMPLE", runner=_capturing_runner(cap, "OK"))
    backend.query("p")
    assert cap["env"].get("CLAUDE_CODE_OAUTH_TOKEN") == "sk-ant-oat01-EXAMPLE"
    assert "ANTHROPIC_API_KEY" not in cap["env"]   # no API key in the override


def test_claude_backend_reads_token_from_env(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-oat01-FROMENV")
    cap: dict = {}
    ClaudeCodeBackend(runner=_capturing_runner(cap, "OK")).query("p")
    assert cap["env"]["CLAUDE_CODE_OAUTH_TOKEN"] == "sk-ant-oat01-FROMENV"


def test_claude_backend_no_token_no_override(monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    cap: dict = {}
    ClaudeCodeBackend(runner=_capturing_runner(cap, "OK")).query("p")
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in cap["env"]


def test_claude_backend_available_with_token(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-oat01-X")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # available() requires the CLI on PATH; assert token-path logic via _oauth_token
    b = ClaudeCodeBackend()
    assert b._oauth_token() == "sk-ant-oat01-X"


def test_oauth_token_allowlisted_for_subprocess():
    from overmind.subprocess_utils import SAFE_ENV_ALLOWLIST
    assert "CLAUDE_CODE_OAUTH_TOKEN" in SAFE_ENV_ALLOWLIST


def test_codex_backend_sets_codex_home_and_readonly(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OVERMIND_CODEX_HOME_MAHMOOD", str(tmp_path))
    cap: dict = {}
    backend = CodexBackend(seat="mahmood", runner=_capturing_runner(cap, "VERDICT: FAIL"))
    backend.query("p")
    assert cap["env"]["CODEX_HOME"] == str(tmp_path)
    assert "--sandbox" in cap["argv"] and "read-only" in cap["argv"]
    assert "--skip-git-repo-check" in cap["argv"]


def test_codex_noreen_seat_uses_distinct_home(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OVERMIND_CODEX_HOME_NOREEN", str(tmp_path / "noreen"))
    cap: dict = {}
    (tmp_path / "noreen").mkdir()
    backend = CodexBackend(seat="noreen", runner=_capturing_runner(cap, "x"))
    backend.query("p")
    assert cap["env"]["CODEX_HOME"].endswith("noreen")


def test_agy_backend_parses_json_text(tmp_path: Path):
    driver = tmp_path / "agy_driver.py"
    driver.write_text("# stub", encoding="utf-8")
    cap: dict = {}
    resp = json.dumps({"text": "VERDICT: PASS\nCONFIDENCE: 0.7", "complete": True})
    backend = AgyBackend(driver_path=str(driver), runner=_capturing_runner(cap, resp))
    out = backend.query("p")
    assert "VERDICT: PASS" in out
    assert "--json" in cap["argv"] and "--model" in cap["argv"]


def test_agy_backend_missing_driver_errors():
    backend = AgyBackend(driver_path=str(Path("does-not-exist.py")))
    out = backend.query("p")
    assert out.startswith(JUDGE_ERROR)


# --- agy async-envelope poll (gap-analysis close #1) ----------------------------

def test_is_async_envelope_detects_wrappers():
    from overmind.verification.judge_backends import is_async_envelope
    # a still-running background-task handle
    assert is_async_envelope(
        "Created At: 2026-07-06T12:33:04Z\nTool is running as a background task with "
        "task id: 379e66d6/task-6\nTask Description: python -c \"import numpy\"") is True
    # a bare command-completed / directory-listing envelope (no answer body)
    assert is_async_envelope("Created At: ...\nCompleted At: ...\n{\"name\":\".ssh\"}") is True
    # a real answer is NEVER an envelope, even if a tool also ran
    assert is_async_envelope("Created At: ...\nFLAG: yes\nREASON: impossible cell") is False
    assert is_async_envelope("FLAG: no\nREASON: fine") is False
    assert is_async_envelope("VERDICT: PASS") is False
    assert is_async_envelope("") is False


def test_agy_backend_prepends_no_tools_directive(tmp_path: Path):
    driver = tmp_path / "agy_driver.py"
    driver.write_text("# stub", encoding="utf-8")
    cap: dict = {}
    resp = json.dumps({"text": "FLAG: no\nREASON: fine", "complete": True})
    AgyBackend(driver_path=str(driver), runner=_capturing_runner(cap, resp)).query("REVIEW THIS")
    prompt_arg = cap["argv"][-1]
    assert "Do NOT run any tools" in prompt_arg and prompt_arg.endswith("REVIEW THIS")


def test_agy_backend_polls_past_envelope_until_real_answer(tmp_path: Path):
    driver = tmp_path / "agy_driver.py"
    driver.write_text("# stub", encoding="utf-8")
    envelope = json.dumps({"text": "Created At: x\nTool is running as a background task "
                                   "with task id: abc/task-1", "complete": True})
    answer = json.dumps({"text": "FLAG: yes\nREASON: comparator swapped", "complete": True})
    calls = {"n": 0}

    def flaky_runner(argv, stdin_text, env_overrides, timeout):
        calls["n"] += 1
        return envelope if calls["n"] == 1 else answer   # 1st = envelope, 2nd = real

    out = AgyBackend(driver_path=str(driver), runner=flaky_runner, max_polls=3).query("p")
    assert "FLAG: yes" in out and calls["n"] == 2   # polled exactly until a real answer


def test_agy_backend_envelope_only_fails_closed(tmp_path: Path):
    driver = tmp_path / "agy_driver.py"
    driver.write_text("# stub", encoding="utf-8")
    envelope = json.dumps({"text": "Created At: x\nTool is running as a background task"})

    def always_envelope(argv, stdin_text, env_overrides, timeout):
        return envelope

    out = AgyBackend(driver_path=str(driver), runner=always_envelope, max_polls=2).query("p")
    assert out.startswith(JUDGE_ERROR) and "envelope" in out   # never masquerades as an answer


def test_agy_backend_recovers_answer_before_trailing_tool_step(tmp_path: Path):
    # the terminal `text` is an envelope, but an earlier MODEL step held the answer
    driver = tmp_path / "agy_driver.py"
    driver.write_text("# stub", encoding="utf-8")
    resp = json.dumps({"text": "Created At: x\nThe command completed",
                       "all_model_text": "FLAG: yes\nREASON: impossible cell\n\nCreated At: x"})
    out = AgyBackend(driver_path=str(driver), runner=_capturing_runner({}, resp), max_polls=2).query("p")
    assert "FLAG: yes" in out


def test_agy_zero_step_fails_loud_never_empty_success(tmp_path: Path):
    """TRIP TEST (Mahmood, agy 0-step fail-open): a 0-step conversation from a
    wedged daemon (`n_steps: 0`, empty text) must return a JUDGE_ERROR — it must
    NEVER be recorded as a clean/empty answer. An empty result from a dead vendor
    is the exact fail-open we close: it can't reach the consensus gate as a vote."""
    driver = tmp_path / "agy_driver.py"
    driver.write_text("# stub", encoding="utf-8")
    zero_step = json.dumps({"text": "", "all_model_text": "", "n_steps": 0, "complete": False})

    out = AgyBackend(driver_path=str(driver),
                     runner=_capturing_runner({}, zero_step), max_polls=2).query("p")
    assert out.startswith(JUDGE_ERROR)
    assert "0-step" in out and "wedged daemon" in out


def test_agy_zero_step_is_an_abstention_never_a_consensus_vote():
    """The 0-step JUDGE_ERROR maps to a non-usable ERROR vendor in the consensus
    gate, so an all-agy-0-step panel flags NO_USABLE_RESPONSES (fail-closed) — a
    dead vendor's silence is never a corroborating vote."""
    from overmind.verification.consensus_gate import (
        VendorResponse, VendorStatus, ConsensusVerdict, FlagReason, resolve_consensus,
    )
    # agy 0-step -> JUDGE_ERROR -> ERROR status, passed=None (not usable)
    responses = [VendorResponse(vendor="agy", status=VendorStatus.ERROR, passed=None)]
    outcome = resolve_consensus(responses)
    assert outcome.verdict == ConsensusVerdict.FLAGGED
    assert FlagReason.NO_USABLE_RESPONSES in outcome.reasons
    assert outcome.passed is False   # a dead vendor never yields a passing consensus


def test_agy_preflight_reap_opt_in_only(tmp_path: Path, monkeypatch):
    """The pre-flight daemon reaper fires only when opted in (reap_stale=True /
    env), never on the default path — so it can't catch the desktop app's daemon
    by surprise."""
    import overmind.reliability.agy_daemon as ad
    driver = tmp_path / "agy_driver.py"
    driver.write_text("# stub", encoding="utf-8")
    resp = json.dumps({"text": "VERDICT: PASS", "complete": True})
    calls = {"n": 0}
    monkeypatch.setattr(ad, "reap_stale_daemons",
                        lambda *a, **k: calls.__setitem__("n", calls["n"] + 1) or [])

    # default: no reap
    AgyBackend(driver_path=str(driver), runner=_capturing_runner({}, resp)).query("p")
    assert calls["n"] == 0
    # opted in: reap runs once before the call
    AgyBackend(driver_path=str(driver), runner=_capturing_runner({}, resp),
               reap_stale=True).query("p")
    assert calls["n"] == 1


def test_local_model_off_by_default():
    backend = LocalModelBackend(enabled=False)
    assert backend.available() is False
    out = backend.query("p")
    assert out.startswith(JUDGE_ERROR)
    assert "disabled" in out


def test_local_model_env_flag_enables(monkeypatch):
    monkeypatch.setenv("OVERMIND_LOCAL_MODEL", "1")
    backend = LocalModelBackend()
    assert backend.available() is True


def test_local_model_uses_injected_http_when_enabled():
    backend = LocalModelBackend(
        enabled=True,
        _http=lambda url, payload, timeout: json.dumps({"response": "VERDICT: PASS"}),
    )
    assert backend.query("p") == "VERDICT: PASS"


# --- SshClaudeBackend (remote subscription-Claude worker over SSH) ---------------

def test_ssh_claude_backend_builds_ssh_argv_and_pipes_stdin():
    from overmind.verification.judge_backends import SshClaudeBackend
    cap: dict = {}
    b = SshClaudeBackend(host="user@1.2.3.4", key=None,
                         remote_cmd="claude -p", runner=_capturing_runner(cap, "FLAG: yes"))
    assert b.query("review this artifact") == "FLAG: yes"
    argv = cap["argv"]
    assert argv[0] == "ssh"
    assert "BatchMode=yes" in argv
    assert argv[-2] == "user@1.2.3.4"      # host
    assert argv[-1] == "claude -p"          # remote command
    assert cap["stdin"] == "review this artifact"   # prompt on stdin


def test_ssh_claude_backend_includes_identity_file_when_key_set():
    from overmind.verification.judge_backends import SshClaudeBackend
    cap: dict = {}
    b = SshClaudeBackend(host="h", key="k.pem", runner=_capturing_runner(cap, "ok"))
    b.query("p")
    argv = cap["argv"]
    assert "-i" in argv and argv[argv.index("-i") + 1] == "k.pem"


def test_ssh_claude_backend_strips_benign_ssh_warning_lines():
    from overmind.verification.judge_backends import SshClaudeBackend
    noisy = ("** WARNING: connection is not using a post-quantum key exchange algorithm.\n"
             "** This session may be vulnerable to store now, decrypt later attacks.\n"
             "FLAG: no\nREASON: clean")
    b = SshClaudeBackend(host="h", runner=lambda *a: noisy)
    out = b.query("p")
    assert out.startswith("FLAG: no")      # warning stripped, real completion preserved
    assert "post-quantum" not in out


def test_ssh_claude_backend_unavailable_without_host():
    from overmind.verification.judge_backends import SshClaudeBackend
    b = SshClaudeBackend(host=None, runner=lambda *a: "x")
    # no host configured (and no env var) -> not available, query returns JUDGE_ERROR
    assert b.available() is False
    assert b.query("p").startswith(JUDGE_ERROR)


def test_ssh_claude_backend_propagates_judge_error_from_runner():
    from overmind.verification.judge_backends import SshClaudeBackend
    b = SshClaudeBackend(host="h", runner=lambda *a: f"{JUDGE_ERROR} exit 255: connection refused")
    assert b.query("p").startswith(JUDGE_ERROR)


def test_ssh_claude_backend_default_remote_cmd_is_portable():
    """Objective gate (hardcoded-local-path P0, Sentinel, 2026-07-06).

    The default remote command must NOT bake in a machine-specific absolute user
    path (e.g. C:\\Users\\<name>\\.local\\bin\\claude.exe). It must be a portable
    bare `claude` the remote node's PATH resolves, so the SSH worker runs on ANY
    node (laptop/pc2/…), not just the one machine where claude sits at that path.
    Fails before the fix (default was the absolute .local\\bin path); passes after.
    Nodes needing a custom path use OVERMIND_CLAUDE_SSH_REMOTE_CMD (tested below).
    """
    import re
    from overmind.verification.judge_backends import SshClaudeBackend

    default_cmd = SshClaudeBackend().remote_cmd
    assert not re.search(r"[A-Za-z]:[\\/]Users[\\/]", default_cmd), default_cmd
    assert "/home/" not in default_cmd, default_cmd
    assert ".local" not in default_cmd, default_cmd
    assert "claude" in default_cmd            # still a runnable claude command


def test_ssh_claude_backend_remote_cmd_env_override(monkeypatch):
    """A node whose non-interactive SSH PATH lacks claude sets an absolute remote
    path via OVERMIND_CLAUDE_SSH_REMOTE_CMD; the backend uses it verbatim over the
    portable default — so portability never removes the escape hatch."""
    from overmind.verification.judge_backends import SshClaudeBackend

    cap: dict = {}
    monkeypatch.setenv("OVERMIND_CLAUDE_SSH_REMOTE_CMD", r'"D:\tools\claude.exe" -p')
    b = SshClaudeBackend(host="h", runner=_capturing_runner(cap, "ok"))
    b.query("p")
    assert cap["argv"][-1] == r'"D:\tools\claude.exe" -p'
