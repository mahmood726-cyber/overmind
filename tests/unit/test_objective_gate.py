"""Tests for the objective-gate floor audit (T12a / WORLD_CLASS_SPEC D2).

The audit is SHADOW-ONLY: it must classify verdicts correctly and WARN on
judge/heuristic-only ships, but it must NEVER change a verdict. These tests lock
both properties.
"""
from __future__ import annotations

import logging

import pytest

from overmind.verification.objective_gate import (
    NON_OBJECTIVE_CHECKS,
    OBJECTIVE_CHECKS,
    ObjectiveGateAudit,
    audit_checks,
    audit_mode,
    audit_result,
    classify_check,
    emit_audit,
)
from overmind.storage.models import VerificationResult


# --- classify_check -------------------------------------------------------------

@pytest.mark.parametrize(
    "check,expected",
    [
        ("build", "objective"),
        ("relevant_tests", "objective"),
        ("numeric_regression", "objective"),
        ("playwright", "objective"),
        ("cross_implementation_parity", "objective"),
        ("verify_command", "objective"),
        ("r_parity", "objective"),
        ("semantic_requirements", "non_objective"),
        ("trajectory_fast_path", "non_objective"),
        ("judge_panel", "non_objective"),        # prefix rule
        ("consensus_vote", "non_objective"),      # prefix rule
        ("quorum_agreement", "non_objective"),    # prefix rule
        ("something_new_check", "unknown"),
    ],
)
def test_classify_check(check, expected):
    assert classify_check(check) == expected


@pytest.mark.parametrize("bad", [None, 123, ["build"], object()])
def test_classify_non_string_is_unknown_not_crash(bad):
    # the shadow audit must never crash on a malformed check list; a non-string
    # entry is 'unknown' (fail-closed: not counted as an objective gate).
    assert classify_check(bad) == "unknown"


def test_audit_checks_survives_non_string_element():
    # a stray non-string in completed_checks must not crash the audit and must not
    # be counted as an objective witness (so a judge-only ship still flags).
    audit = audit_checks("t", True, ["semantic_requirements", None, 42])
    assert audit.would_ship_without_gate is True
    assert audit.objective_gate_present is False
    assert None in audit.unknown_checks and 42 in audit.unknown_checks


def test_classify_strips_detail_suffix():
    # completed/skipped checks sometimes carry a ": detail" suffix
    assert classify_check("build: exit=0 command=make") == "objective"
    assert classify_check("semantic_requirements: judge pass") == "non_objective"


def test_taxonomy_sets_are_disjoint():
    assert OBJECTIVE_CHECKS.isdisjoint(NON_OBJECTIVE_CHECKS)


# --- audit_checks ---------------------------------------------------------------

def test_objective_witness_present_no_warn():
    audit = audit_checks("t1", True, ["build", "relevant_tests", "semantic_requirements"])
    assert audit.objective_gate_present is True
    assert audit.would_ship_without_gate is False
    assert "build" in audit.objective_checks
    assert "semantic_requirements" in audit.non_objective_checks


def test_judge_only_ship_is_flagged():
    audit = audit_checks("t2", True, ["semantic_requirements"])
    assert audit.objective_gate_present is False
    assert audit.would_ship_without_gate is True


def test_trajectory_fast_path_only_is_flagged():
    # a probabilistic skip with no objective witness must flag
    audit = audit_checks("t3", True, ["trajectory_fast_path"])
    assert audit.would_ship_without_gate is True


def test_unknown_check_does_not_count_as_gate():
    # fail-closed: an unrecognised check is not an objective floor
    audit = audit_checks("t4", True, ["mystery_check"])
    assert audit.objective_gate_present is False
    assert audit.would_ship_without_gate is True
    assert audit.unknown_checks == ["mystery_check"]


def test_failed_verdict_never_flagged():
    # would_ship_without_gate only concerns *success* verdicts
    audit = audit_checks("t5", False, ["semantic_requirements"])
    assert audit.would_ship_without_gate is False


def test_empty_checks_success_is_flagged():
    audit = audit_checks("t6", True, [])
    assert audit.would_ship_without_gate is True


# --- audit_result on the real dataclass ----------------------------------------

def test_audit_result_reads_verification_result():
    vr = VerificationResult(
        task_id="tid",
        success=True,
        required_checks=["build"],
        completed_checks=["build"],
        skipped_checks=[],
        details=[],
    )
    audit = audit_result(vr)
    assert isinstance(audit, ObjectiveGateAudit)
    assert audit.objective_gate_present is True
    assert audit.to_dict()["would_ship_without_gate"] is False


# --- emit_audit: shadow behaviour + mode ----------------------------------------

def test_emit_audit_off_returns_none(monkeypatch):
    monkeypatch.setenv("OVERMIND_OBJECTIVE_GATE_AUDIT", "off")
    assert audit_mode() == "off"
    vr = VerificationResult("t", True, ["build"], ["build"], [], [])
    assert emit_audit(vr) is None


def test_emit_audit_default_is_shadow(monkeypatch):
    monkeypatch.delenv("OVERMIND_OBJECTIVE_GATE_AUDIT", raising=False)
    assert audit_mode() == "shadow"


def test_emit_audit_warns_on_judge_only(monkeypatch, caplog):
    monkeypatch.setenv("OVERMIND_OBJECTIVE_GATE_AUDIT", "shadow")
    vr = VerificationResult("tj", True, ["semantic_requirements"], ["semantic_requirements"], [], [])
    with caplog.at_level(logging.WARNING):
        audit = emit_audit(vr)
    assert audit is not None
    assert audit.would_ship_without_gate is True
    assert any("WOULD-SHIP-WITHOUT-OBJECTIVE-GATE" in r.message for r in caplog.records)


def test_emit_audit_silent_when_gate_present(monkeypatch, caplog):
    monkeypatch.setenv("OVERMIND_OBJECTIVE_GATE_AUDIT", "shadow")
    vr = VerificationResult("tg", True, ["build"], ["build"], [], [])
    with caplog.at_level(logging.WARNING):
        emit_audit(vr)
    assert not any("WOULD-SHIP-WITHOUT-OBJECTIVE-GATE" in r.message for r in caplog.records)


def test_emit_audit_does_not_mutate_result(monkeypatch):
    monkeypatch.setenv("OVERMIND_OBJECTIVE_GATE_AUDIT", "shadow")
    vr = VerificationResult("tm", True, ["semantic_requirements"], ["semantic_requirements"], [], [])
    before = (vr.task_id, vr.success, list(vr.completed_checks))
    emit_audit(vr)
    after = (vr.task_id, vr.success, list(vr.completed_checks))
    assert before == after
