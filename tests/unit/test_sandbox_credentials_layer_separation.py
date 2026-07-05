"""A2 no-regression proof: Claude Code `sandbox.credentials` vs Overmind's own
subprocess credential path are SEPARATE layers.

Context (cc-adopt-4 win A2, 2026-07-05): a `managed-settings.json`
`sandbox.credentials` block was added on the autonomous node to deny Claude
Code's *own sandboxed bash* from reading CLAUDE_CODE_OAUTH_TOKEN / Anthropic /
Gemini env vars and the Codex/agy/Claude credential files (defense-in-depth
against a sandboxed command exfiltrating on-disk subscription creds).

That setting governs the Claude Code sandbox only. The Overmind Claude *judge
lane* (`ClaudeCodeBackend` -> `claude -p`) does NOT run through Claude Code's
sandboxed bash — it is launched by Overmind's own Python via
``judge_backends._default_runner``, whose environment is built by
``subprocess_utils.safe_subprocess_env()`` (an independent allowlist that
DELIBERATELY passes CLAUDE_CODE_OAUTH_TOKEN so headless `claude -p` authenticates
on the subscription).

These tests pin that separation: adding `sandbox.credentials` must not, and
structurally cannot, strip the OAuth token from the Overmind judge lane. If a
future refactor routed the judge through the CC sandbox or dropped the token
from the allowlist, these assertions fail — that is the regression signal.
"""
from __future__ import annotations

from overmind.subprocess_utils import SAFE_ENV_ALLOWLIST, safe_subprocess_env
from overmind.verification import judge_backends
from overmind.verification.judge_backends import ClaudeCodeBackend


def test_oauth_token_survives_the_overmind_allowlist(monkeypatch):
    """The token the Claude judge lane needs is allowlisted AND survives scrubbing.

    This is the layer `sandbox.credentials` does not touch; it must keep working.
    """
    assert "CLAUDE_CODE_OAUTH_TOKEN" in SAFE_ENV_ALLOWLIST
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-oat01-JUDGE-LANE")
    # A hostile/unrelated var must be scrubbed; the auth token must remain.
    monkeypatch.setenv("LD_PRELOAD", "/evil.so")
    env = safe_subprocess_env()
    assert env.get("CLAUDE_CODE_OAUTH_TOKEN") == "sk-ant-oat01-JUDGE-LANE"
    assert "LD_PRELOAD" not in env


def test_token_lands_in_the_real_subprocess_env(monkeypatch):
    """End-to-end: the env actually handed to subprocess.run for `claude -p`
    contains the OAuth token — proving headless auth still reaches the lane."""
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-oat01-E2E")
    captured: dict = {}

    class _FakeCompleted:
        returncode = 0
        stdout = "VERDICT: PASS"
        stderr = ""

    def _fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["env"] = kwargs.get("env", {})
        return _FakeCompleted()

    # Patch subprocess.run inside the module so _default_runner builds the REAL
    # env (safe_subprocess_env() + auth override) without spawning a CLI.
    monkeypatch.setattr(judge_backends.subprocess, "run", _fake_run)

    out = ClaudeCodeBackend().query("judge this diff")
    assert out == "VERDICT: PASS"
    # The token reached the subprocess env: this is the headless-auth path that
    # sandbox.credentials must not (and does not) break.
    assert captured["env"].get("CLAUDE_CODE_OAUTH_TOKEN") == "sk-ant-oat01-E2E"
    assert captured["argv"][0].lower().find("claude") != -1


def test_sandbox_credentials_is_not_the_overmind_env_path():
    """Guard-rail doc-test: Overmind's subprocess env path is `safe_subprocess_env`,
    which has no knowledge of Claude Code's `sandbox.credentials`. The two are
    orthogonal — this asserts the allowlist remains the single source of truth for
    what the judge subprocess inherits (so the CC-layer deny cannot silently
    govern it)."""
    # The allowlist is the ONLY gate on the judge subprocess env; it explicitly
    # includes the auth token and excludes everything else by default.
    assert "CLAUDE_CODE_OAUTH_TOKEN" in SAFE_ENV_ALLOWLIST
    assert "ANTHROPIC_API_KEY" in SAFE_ENV_ALLOWLIST
    # A representative non-allowlisted secret-bearing var is NOT inherited.
    assert "GITHUB_TOKEN" not in SAFE_ENV_ALLOWLIST
