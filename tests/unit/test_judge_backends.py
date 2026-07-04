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
