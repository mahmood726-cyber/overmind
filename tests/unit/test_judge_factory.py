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
from overmind.verification.llm_judge import GeminiBackend, LLMJudge, QuorumJudge, RoutedJudge, StubBackend


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


def test_fallback_to_secondary_warns(caplog):
    """A silent downgrade to a non-primary backend must be observable (agy
    review point): emit a WARNING naming the backend that actually served."""
    import logging
    over_quota = _FakeBackend("primary", f"{JUDGE_ERROR} 429")
    secondary = _FakeBackend("secondary", "VERDICT: PASS")
    with caplog.at_level(logging.WARNING, logger="overmind.verification.judge_backends"):
        FallbackBackend(backends=[over_quota, secondary]).query("p")
    assert any("fell back" in r.message or "fell back" in r.getMessage() for r in caplog.records)


# ── CoT + rubric prompt toggle (A3) ─────────────────────────────────


def test_cot_on_by_default(monkeypatch):
    # A3: CoT defaults ON after the golden-set no-regression gate.
    monkeypatch.delenv("OVERMIND_JUDGE_COT", raising=False)
    judge = jf.build_judge(spec="stub")
    assert judge.use_cot is True


def test_cot_disabled_via_env(monkeypatch):
    monkeypatch.setenv("OVERMIND_JUDGE_COT", "0")
    judge = jf.build_judge(spec="stub")
    assert judge.use_cot is False


def test_cot_param_overrides_env(monkeypatch):
    monkeypatch.setenv("OVERMIND_JUDGE_COT", "0")
    judge = jf.build_judge(spec="stub", use_cot=True)
    assert judge.use_cot is True


def test_cot_enabled_via_env(monkeypatch):
    monkeypatch.setenv("OVERMIND_JUDGE_COT", "1")
    judge = jf.build_judge(spec="stub")
    assert judge.use_cot is True


def test_cot_prompt_contains_rubric_and_reasoning():
    from overmind.storage.models import ProjectRecord, TaskRecord, VerificationResult

    backend = StubBackend()
    judge = LLMJudge(backend=backend, use_cot=True)
    task = TaskRecord(
        task_id="t1", project_id="p1", title="do a thing", task_type="verification",
        source="auto", priority=0.8, risk="medium", expected_runtime_min=5,
        expected_context_cost="low", required_verification=["tests pass"],
    )
    project = ProjectRecord(project_id="p1", name="proj", root_path="C:\\tmp\\p")
    vr = VerificationResult(task_id="t1", success=True, required_checks=["tests"],
                            completed_checks=["tests"], skipped_checks=[], details=[])
    judge.judge(task, project, vr)
    assert backend.last_prompt is not None
    assert "Think step by step" in backend.last_prompt
    assert "RELEVANCE" in backend.last_prompt and "EVIDENCE" in backend.last_prompt
    # The structured output contract must remain so _parse_verdict still works.
    assert "VERDICT: PASS or FAIL" in backend.last_prompt


def test_quorum_propagates_cot_flag():
    judge = jf.build_judge(spec="stub,gemini,claude", mode="quorum", use_cot=True)
    assert isinstance(judge, QuorumJudge)
    assert all(j.use_cot for j in judge.judges)


# ── effective-vote / different-family decorrelation (A2) ─────────────


def test_same_family_quorum_flags_low_effective_votes():
    # claude (anthropic) + codex (openai) + codex-noreen (openai): 3 nominal,
    # 2 families → fewer effective votes than nominal.
    ev = jf.estimate_effective_votes(["claude", "codex", "codex-noreen"])
    assert ev.nominal == 3
    assert ev.distinct_families == 2
    assert ev.effective_votes < ev.nominal
    assert ev.warning is not None


def test_all_same_family_quorum_warns_hardest():
    ev = jf.estimate_effective_votes(["claude", "claude", "claude"])
    assert ev.distinct_families == 1
    assert ev.effective_votes < 3
    assert "correlated" in ev.warning


def test_all_different_families_no_warning():
    # claude (anthropic) + gemini (google) + local (local): fully decorrelated.
    ev = jf.estimate_effective_votes(["claude", "gemini", "local"])
    assert ev.distinct_families == 3
    assert ev.effective_votes == 3
    assert ev.warning is None


def test_agy_and_gemini_are_same_family():
    # Both ride Google/Gemini — must not be counted as independent.
    assert jf.family_for_engine("agy") == jf.family_for_engine("gemini")
    ev = jf.estimate_effective_votes(["agy", "gemini"])
    assert ev.distinct_families == 1
    assert ev.warning is not None


def test_quorum_verdict_carries_effective_votes(caplog):
    import logging
    from overmind.storage.models import ProjectRecord, TaskRecord, VerificationResult

    with caplog.at_level(logging.WARNING, logger="overmind.verification.judge_factory"):
        # enforce_families=False: this test exercises the warn-only effective-vote
        # SURFACING path (a correlated panel still runs). Hard enforcement is
        # covered separately in test_quorum_enforcement_*.
        judge = jf.build_judge(spec="claude,codex,codex-noreen", mode="quorum",
                               enforce_families=False)
    # Build-time warning fired about correlated panel.
    assert any("effective" in r.getMessage() or "correlated" in r.getMessage()
               for r in caplog.records)
    assert judge.nominal_votes == 3
    assert judge.effective_votes < 3
    assert judge.distinct_families == 2

    # Swap the live backends for deterministic stubs so the verdict is offline.
    for j in judge.judges:
        j.backend = StubBackend()
    task = TaskRecord(
        task_id="t1", project_id="p1", title="x", task_type="verification",
        source="auto", priority=0.8, risk="medium", expected_runtime_min=5,
        expected_context_cost="low", required_verification=["tests"],
    )
    project = ProjectRecord(project_id="p1", name="proj", root_path="C:\\tmp\\p")
    vr = VerificationResult(task_id="t1", success=True, required_checks=["tests"],
                            completed_checks=["tests"], skipped_checks=[], details=[])
    verdict = judge.judge(task, project, vr)
    assert verdict.nominal_votes == 3
    assert verdict.effective_votes < 3
    assert "quorum_correlated_panel" in verdict.concerns


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


# ── A2 hard-enforcement of different-family quorum panels ────────────


def test_enforce_distinct_families_drops_same_family_redundancy():
    e = jf.enforce_distinct_families(["claude", "codex", "codex-noreen"])
    assert e.action == "repaired"
    assert e.rejected_quorum is False
    assert e.repaired == ["claude", "codex"]      # one per family, order-preserving
    assert e.dropped == ["codex-noreen"]


def test_enforce_distinct_families_rejects_single_family():
    e = jf.enforce_distinct_families(["claude", "claude"])
    assert e.action == "rejected"
    assert e.rejected_quorum is True
    assert e.repaired == ["claude"]


def test_enforce_distinct_families_passthrough_when_all_distinct():
    e = jf.enforce_distinct_families(["claude", "codex", "gemini"])
    assert e.action == "unchanged"
    assert e.repaired == ["claude", "codex", "gemini"]
    assert e.dropped == []


def test_enforce_agy_and_gemini_collapse():
    # agy and gemini are both Google -> only one survives.
    e = jf.enforce_distinct_families(["agy", "gemini", "codex"])
    assert e.action == "repaired"
    assert e.repaired == ["agy", "codex"]


def test_build_judge_default_enforces_distinct_family_quorum():
    # Default (enforce on): a 3-engine / 2-family panel is repaired to 2 judges,
    # and the surviving quorum no longer overcounts independence.
    judge = jf.build_judge(spec="claude,codex,codex-noreen", mode="quorum")
    assert isinstance(judge, QuorumJudge)
    assert len(judge.judges) == 2
    assert judge.distinct_families == 2
    assert judge.effective_votes == judge.nominal_votes == 2


def test_build_judge_enforce_rejects_single_family_quorum_to_fallback():
    # A same-family-only "quorum" is not a real quorum: enforcement falls back to
    # a single-engine chain rather than advertising false independence.
    judge = jf.build_judge(spec="codex,codex-noreen", mode="quorum")
    assert isinstance(judge, LLMJudge)
    assert isinstance(judge.backend, FallbackBackend)


def test_build_judge_enforce_off_preserves_correlated_panel():
    # Escape hatch: enforce_families=False keeps the old warn-only behavior.
    judge = jf.build_judge(spec="claude,codex,codex-noreen", mode="quorum",
                           enforce_families=False)
    assert isinstance(judge, QuorumJudge)
    assert len(judge.judges) == 3


def test_quorum_enforce_env_toggle(monkeypatch):
    monkeypatch.setenv("OVERMIND_JUDGE_QUORUM_ENFORCE", "0")
    judge = jf.build_judge(spec="claude,codex,codex-noreen", mode="quorum")
    assert isinstance(judge, QuorumJudge)
    assert len(judge.judges) == 3
    monkeypatch.setenv("OVERMIND_JUDGE_QUORUM_ENFORCE", "1")
    judge2 = jf.build_judge(spec="claude,codex,codex-noreen", mode="quorum")
    assert len(judge2.judges) == 2


# ── C2 cost-aware routed judge ──────────────────────────────────────


def _route_inputs():
    from overmind.storage.models import ProjectRecord, TaskRecord, VerificationResult
    task = TaskRecord(
        task_id="t", project_id="p", title="x", task_type="verification",
        source="auto", priority=0.8, risk="medium", expected_runtime_min=5,
        expected_context_cost="low", required_verification=["tests"],
    )
    project = ProjectRecord(project_id="p", name="proj", root_path="C:\\tmp\\p")
    vr = VerificationResult(task_id="t", success=True, required_checks=["tests"],
                            completed_checks=["tests"], skipped_checks=[], details=[])
    return task, project, vr


def _resp(verdict, conf):
    return f"VERDICT: {verdict}\nCONFIDENCE: {conf}\nREASONING: r\nCONCERNS: none\nMET: x\nMISSED: none"


def test_build_judge_routed_mode_constructs_routed_judge():
    judge = jf.build_judge(spec="local,claude,gemini", mode="routed")
    assert isinstance(judge, RoutedJudge)
    # escalation tier is a cross-family quorum (claude+gemini)
    assert isinstance(judge.expensive_judge, QuorumJudge)
    assert isinstance(judge.cheap_judge, LLMJudge)


def test_routed_accepts_confident_cheap_no_escalation():
    from overmind.verification.llm_judge import RoutedJudge as RJ
    cheap = LLMJudge(backend=StubBackend(response=_resp("FAIL", 0.92)))
    expensive = LLMJudge(backend=StubBackend(response=_resp("PASS", 0.99)))
    routed = RJ(cheap_judge=cheap, expensive_judge=expensive)
    v = routed.judge(*_route_inputs())
    assert v.passed is False                      # cheap verdict used
    assert "routed_cheap_accepted" in v.concerns
    assert "routed_escalated" not in v.concerns


def test_routed_escalates_on_low_confidence():
    from overmind.verification.llm_judge import RoutedJudge as RJ
    cheap = LLMJudge(backend=StubBackend(response=_resp("PASS", 0.55)))
    expensive = LLMJudge(backend=StubBackend(response=_resp("FAIL", 0.95)))
    routed = RJ(cheap_judge=cheap, expensive_judge=expensive)
    v = routed.judge(*_route_inputs())
    assert v.passed is False                      # expensive verdict used
    assert "routed_escalated" in v.concerns


def test_routed_pass_below_floor_escalates():
    # A cheap PASS above the general threshold (0.75) but below the higher PASS
    # floor (0.85) must still escalate — the truth-first asymmetry.
    from overmind.verification.llm_judge import RoutedJudge as RJ
    cheap = LLMJudge(backend=StubBackend(response=_resp("PASS", 0.80)))
    expensive = LLMJudge(backend=StubBackend(response=_resp("FAIL", 0.95)))
    routed = RJ(cheap_judge=cheap, expensive_judge=expensive)
    v = routed.judge(*_route_inputs())
    assert v.passed is False
    assert "routed_escalated" in v.concerns


def test_routed_escalates_on_degenerate_cheap():
    from overmind.verification.llm_judge import RoutedJudge as RJ
    cheap = LLMJudge(backend=StubBackend(response=""))   # degenerate
    expensive = LLMJudge(backend=StubBackend(response=_resp("PASS", 0.95)))
    routed = RJ(cheap_judge=cheap, expensive_judge=expensive)
    v = routed.judge(*_route_inputs())
    assert v.passed is True
    assert "routed_escalated" in v.concerns
