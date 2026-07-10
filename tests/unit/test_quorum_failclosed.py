"""Fail-closed enforcement of the quorum consensus outcome in the LIVE path
(hardening/quorum-failclosed-2026-07-10).

W-A: QuorumJudge used to fail OPEN — a threshold-PASS could be recorded as an
     independent-judge gate even when too few backends responded.
W-B: the correlated-panel / Kish n_eff floor (decorrelation_gate) was recorded
     observationally but never enforced in the decision.

These tests prove the deterministic consensus outcome is now attached to the
QuorumVerdict and separates a real decorrelated agreement from a flagged one —
WITHOUT changing QuorumVerdict.passed (the preserved contract). The
orchestrator-level enforcement is covered in
tests/integration/test_orchestrator_run_once.py.
"""
from __future__ import annotations

from overmind.storage.models import ProjectRecord, TaskRecord, VerificationResult
from overmind.verification.consensus_gate import ConsensusVerdict, FlagReason
from overmind.verification.llm_judge import LLMJudge, QuorumJudge, StubBackend


def _task() -> TaskRecord:
    return TaskRecord(
        task_id="t", project_id="p", title="t", task_type="verification",
        source="test", priority=0.5, risk="medium", expected_runtime_min=1,
        expected_context_cost="low", required_verification=["relevant_tests"],
    )


def _project() -> ProjectRecord:
    return ProjectRecord(project_id="p", name="p", root_path="/tmp/p")


def _result() -> VerificationResult:
    return VerificationResult(
        task_id="t", success=True, required_checks=["relevant_tests"],
        completed_checks=["relevant_tests"], skipped_checks=[], details=[], trace_id="t",
    )


def _judge(response: str) -> LLMJudge:
    return LLMJudge(backend=StubBackend(response=response))


_PASS = "VERDICT: PASS\nCONFIDENCE: 0.9\nREASONING: ok"
_FAIL = "VERDICT: FAIL\nCONFIDENCE: 0.8\nREASONING: nope"
_ERROR = "JUDGE_ERROR: backend down"
_MALFORMED = "totally unparseable, no verdict token here"


def _quorum(engines, responses, **kw):
    judges = [_judge(r) for r in responses]
    return QuorumJudge(judges=judges, engines=engines, **kw)


# --- decorrelated unanimous PASS: not flagged ----------------------------------

def test_decorrelated_unanimous_pass_not_flagged():
    q = _quorum(["claude", "codex"], [_PASS, _PASS])
    v = q.judge(_task(), _project(), _result())
    assert v.passed is True
    assert v.consensus_outcome is not None
    assert v.consensus_outcome.verdict == ConsensusVerdict.CONSENSUS_PASS
    assert v.consensus_outcome.flagged is False
    assert set(v.consensus_outcome.witnesses) == {"claude", "codex"}


# --- W-B: correlated panel PASS -> FLAGGED, but .passed unchanged (contract) ----

def test_correlated_panel_pass_is_flagged_but_passed_unchanged():
    q = _quorum(["claude", "claude"], [_PASS, _PASS])
    v = q.judge(_task(), _project(), _result())
    # CONTRACT PRESERVED: threshold-based .passed still True ...
    assert v.passed is True
    # ... but the deterministic outcome flags the correlated panel.
    assert v.consensus_outcome.verdict == ConsensusVerdict.FLAGGED
    assert FlagReason.CORRELATED_PANEL in v.consensus_outcome.reasons


# --- W-A: partial availability -> FLAGGED insufficient witnesses ----------------

def test_partial_availability_one_error_is_flagged():
    q = _quorum(["claude", "codex"], [_PASS, _ERROR])
    v = q.judge(_task(), _project(), _result())
    # one usable PASS => threshold .passed True (open), but outcome flags it.
    assert v.passed is True
    assert v.consensus_outcome.verdict == ConsensusVerdict.FLAGGED
    assert FlagReason.INSUFFICIENT_WITNESSES in v.consensus_outcome.reasons
    assert v.consensus_outcome.n_usable == 1


def test_all_backends_error_unreachable_path_flags():
    q = _quorum(["claude", "codex"], [_ERROR, _ERROR])
    v = q.judge(_task(), _project(), _result())
    assert "judge_error" in v.concerns and "quorum_unreachable" in v.concerns
    # the unreachable early-return still carries a fail-closed outcome
    assert v.consensus_outcome.verdict == ConsensusVerdict.FLAGGED
    assert FlagReason.NO_USABLE_RESPONSES in v.consensus_outcome.reasons


def test_malformed_output_is_abstention():
    q = _quorum(["claude", "codex"], [_PASS, _MALFORMED])
    v = q.judge(_task(), _project(), _result())
    # malformed reply is a non-vote -> only 1 usable -> flagged
    assert v.consensus_outcome.verdict == ConsensusVerdict.FLAGGED
    assert FlagReason.INSUFFICIENT_WITNESSES in v.consensus_outcome.reasons
    assert v.consensus_outcome.n_usable == 1


def test_disagreement_is_flagged():
    q = _quorum(["claude", "codex"], [_PASS, _FAIL])
    v = q.judge(_task(), _project(), _result())
    assert v.consensus_outcome.verdict == ConsensusVerdict.FLAGGED
    assert FlagReason.DISAGREEMENT in v.consensus_outcome.reasons


def test_three_families_unanimous_pass_is_consensus():
    q = _quorum(["claude", "codex", "agy"], [_PASS, _PASS, _PASS])
    v = q.judge(_task(), _project(), _result())
    assert v.consensus_outcome.verdict == ConsensusVerdict.CONSENSUS_PASS
    assert v.consensus_outcome.distinct_families == 3


# --- legacy construction (no engines): outcome is None, behavior unchanged ------

def test_engineless_quorum_has_no_consensus_outcome():
    q = QuorumJudge(judges=[_judge(_PASS), _judge(_PASS)])  # no engines
    v = q.judge(_task(), _project(), _result())
    assert v.passed is True
    assert v.consensus_outcome is None


def test_engine_length_mismatch_is_ignored_safely():
    # defensive: engines list not aligned with judges -> outcome None, no crash.
    q = QuorumJudge(judges=[_judge(_PASS), _judge(_PASS)], engines=["claude"])
    v = q.judge(_task(), _project(), _result())
    assert v.consensus_outcome is None
