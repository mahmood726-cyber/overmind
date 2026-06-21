"""Tests for the engine-pluggable judge factory + fallback (P2-12 / design 1).

Proves, without any live call or quota burn:
  - every named engine is selectable and builds the right backend
  - the fallback chain skips unavailable / over-quota engines and uses the
    next usable one
  - quorum mode builds a QuorumJudge over multiple engines
  - unknown engine names degrade to the default chain (fail-soft)
"""
from __future__ import annotations

import pytest

from overmind.verification import judge_factory as jf
from overmind.verification.judge_backends import (
    AgyBackend,
    ClaudeCodeBackend,
    CodexBackend,
    FallbackBackend,
    LocalModelBackend,
    JUDGE_ERROR,
)
from overmind.verification.llm_judge import GeminiBackend, LLMJudge, QuorumJudge, StubBackend


# ── engine selection ────────────────────────────────────────────────


@pytest.mark.parametrize("engine,cls", [
    ("claude", ClaudeCodeBackend),
    ("codex", CodexBackend),
    ("codex-noreen", CodexBackend),
    ("agy", AgyBackend),
    ("gemini", GeminiBackend),
    ("local", LocalModelBackend),
    ("stub", StubBackend),
])
def test_every_engine_is_selectable(engine, cls):
    backend = jf.build_backend(engine)
    assert isinstance(backend, cls)


def test_codex_seats_distinct():
    assert jf.build_backend("codex").seat == "mahmood"
    assert jf.build_backend("codex-noreen").seat == "noreen"


def test_known_engines_constant_matches_builders():
    assert jf.KNOWN_ENGINES == frozenset(jf.ENGINE_BUILDERS)


# ── spec parsing / fail-soft ────────────────────────────────────────


def test_default_chain_when_unset():
    assert jf._parse_engine_spec(None) == list(jf.DEFAULT_ENGINE_CHAIN)


def test_unknown_engine_dropped_keeps_known():
    assert jf._parse_engine_spec("gemini,bogus,codex") == ["gemini", "codex"]


def test_all_unknown_falls_back_to_default():
    assert jf._parse_engine_spec("nope,bogus") == list(jf.DEFAULT_ENGINE_CHAIN)


def test_semicolon_separator_supported():
    assert jf._parse_engine_spec("claude; gemini") == ["claude", "gemini"]


# ── judge construction ──────────────────────────────────────────────


def test_single_engine_builds_fallback_wrapped_llmjudge():
    judge = jf.build_judge(spec="stub", mode="fallback")
    assert isinstance(judge, LLMJudge)
    assert isinstance(judge.backend, FallbackBackend)


def test_quorum_mode_builds_quorum_over_engines():
    judge = jf.build_judge(spec="stub,gemini,claude", mode="quorum")
    assert isinstance(judge, QuorumJudge)
    assert len(judge.judges) == 3


def test_quorum_with_single_engine_degrades_to_fallback():
    judge = jf.build_judge(spec="stub", mode="quorum")
    assert isinstance(judge, LLMJudge)


def test_env_drives_selection(monkeypatch):
    monkeypatch.setenv("OVERMIND_JUDGE_ENGINE", "stub")
    monkeypatch.setenv("OVERMIND_JUDGE_MODE", "fallback")
    judge = jf.build_judge()
    assert isinstance(judge, LLMJudge)


# ── fallback behaviour ──────────────────────────────────────────────


class _FakeBackend:
    def __init__(self, name, response, available=True):
        self._name = name
        self._response = response
        self._available = available
        self.calls = 0

    def available(self):
        return self._available

    def query(self, prompt):
        self.calls += 1
        return self._response


def test_fallback_skips_unavailable_uses_next():
    down = _FakeBackend("down", "VERDICT: PASS", available=False)
    up = _FakeBackend("up", "VERDICT: PASS\nCONFIDENCE: 0.9")
    fb = FallbackBackend(backends=[down, up])
    out = fb.query("p")
    assert "VERDICT: PASS" in out
    assert down.calls == 0  # never called — availability gated
    assert up.calls == 1


def test_fallback_over_quota_primary_falls_through():
    over_quota = _FakeBackend("primary", f"{JUDGE_ERROR} 429 quota exceeded")
    secondary = _FakeBackend("secondary", "VERDICT: FAIL\nCONFIDENCE: 0.8")
    fb = FallbackBackend(backends=[over_quota, secondary])
    out = fb.query("p")
    assert "VERDICT: FAIL" in out
    assert over_quota.calls == 1 and secondary.calls == 1


def test_fallback_all_failed_returns_judge_error():
    a = _FakeBackend("a", f"{JUDGE_ERROR} down", available=False)
    b = _FakeBackend("b", f"{JUDGE_ERROR} 500")
    out = FallbackBackend(backends=[a, b]).query("p")
    assert out.startswith(JUDGE_ERROR)
    assert "all judge backends failed" in out


def test_fallback_first_usable_wins_short_circuits():
    first = _FakeBackend("first", "VERDICT: PASS")
    second = _FakeBackend("second", "VERDICT: FAIL")
    FallbackBackend(backends=[first, second]).query("p")
    assert second.calls == 0  # short-circuited after first success


# ── end-to-end through LLMJudge.judge (no live call) ────────────────


def test_judge_uses_fallback_secondary_for_real_verdict():
    """A full judge() call where the primary is over quota and the secondary
    returns a parseable PASS verdict — proves wiring end to end with no quota."""
    from overmind.storage.models import ProjectRecord, TaskRecord, VerificationResult

    primary = _FakeBackend("primary", f"{JUDGE_ERROR} quota")
    secondary = _FakeBackend(
        "secondary",
        "VERDICT: PASS\nCONFIDENCE: 0.91\nREASONING: ok\nCONCERNS: none\nMET: all\nMISSED: none",
    )
    judge = LLMJudge(backend=FallbackBackend(backends=[primary, secondary]))
    task = TaskRecord(
        task_id="t1", project_id="p1", title="do a thing",
        task_type="verification", source="auto", priority=0.8, risk="medium",
        expected_runtime_min=5, expected_context_cost="low",
        required_verification=["tests pass"],
    )
    project = ProjectRecord(project_id="p1", name="proj", root_path="C:\\tmp\\p")
    vr = VerificationResult(
        task_id="t1", success=True, required_checks=["tests"],
        completed_checks=["tests"], skipped_checks=[], details=[],
    )
    verdict = judge.judge(task, project, vr, transcript_lines=["did the thing"])
    assert verdict.passed is True
    assert verdict.confidence == pytest.approx(0.91)
    assert "judge_error" not in verdict.concerns
