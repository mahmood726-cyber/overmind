"""Tests for the fail-closed consensus-or-flag resolver
(hardening/consensus-verifier-2026-07-10).

Covers the branch targets:
  #1 consensus-or-flag edge cases — partial availability, timeout, malformed
     output, near-miss vs real disagreement; harness must FAIL-CLOSED.
  #2 tolerance discipline — explicit, documented, boundary-tested (just-inside
     vs just-outside).
  #3 provenance/witness binding — outcome carries which vendors witnessed it, and
     a sub-quorum / correlated panel is flagged, never passed.
  #4 seeded-disagreement regression — a planted vendor split asserts a FLAG.

Pure module: no CLI, no network, no clock. Every case is deterministic.
"""
from __future__ import annotations

import json

import pytest

from overmind.verification.consensus_gate import (
    DEFAULT_ATOL,
    DEFAULT_RTOL,
    ConsensusVerdict,
    FlagReason,
    NumericAgreement,
    VendorResponse,
    VendorStatus,
    numeric_consensus,
    resolve_consensus,
)


def _ok(vendor: str, passed: bool, value: float | None = None) -> VendorResponse:
    return VendorResponse(vendor=vendor, status=VendorStatus.OK, passed=passed, value=value)


# --- happy path: decorrelated unanimous PASS -----------------------------------

def test_two_independent_families_unanimous_pass_is_consensus():
    out = resolve_consensus([_ok("claude", True), _ok("codex", True)])
    assert out.verdict == ConsensusVerdict.CONSENSUS_PASS
    assert out.passed is True
    assert out.flagged is False
    assert set(out.witnesses) == {"claude", "codex"}
    assert set(out.witness_families) == {"anthropic", "openai"}
    assert out.distinct_families == 2
    assert out.effective_votes == pytest.approx(2.0)
    assert out.reasons == []


def test_three_families_unanimous_pass():
    out = resolve_consensus([_ok("claude", True), _ok("codex", True), _ok("agy", True)])
    assert out.verdict == ConsensusVerdict.CONSENSUS_PASS
    assert out.distinct_families == 3


# --- W2/W5/#3: correlated panel & sub-quorum flag, never pass -------------------

def test_same_family_unanimous_pass_is_flagged_correlated():
    # two Anthropic judges agreeing is ~1 effective vote — NOT consensus.
    out = resolve_consensus([_ok("claude", True), _ok("claude", True)])
    assert out.verdict == ConsensusVerdict.FLAGGED
    assert FlagReason.CORRELATED_PANEL in out.reasons
    assert out.distinct_families == 1
    assert out.effective_votes < 2.0


def test_single_vendor_pass_is_insufficient_witnesses():
    out = resolve_consensus([_ok("claude", True)])
    assert out.verdict == ConsensusVerdict.FLAGGED
    assert FlagReason.INSUFFICIENT_WITNESSES in out.reasons
    # also correlated (1 family) — both floors reported
    assert FlagReason.CORRELATED_PANEL in out.reasons


def test_pass_floor_can_be_relaxed_explicitly():
    # a caller that deliberately accepts a single witness must say so; the default
    # is fail-closed.
    out = resolve_consensus(
        [_ok("claude", True)],
        min_usable_witnesses=1,
        min_independent_families=1,
        min_effective_votes=1.0,
    )
    assert out.verdict == ConsensusVerdict.CONSENSUS_PASS


# --- #1: partial availability / timeout / error / unavailable ------------------

def test_one_of_n_responds_rest_timeout_is_flagged():
    out = resolve_consensus([
        _ok("claude", True),
        VendorResponse("codex", status=VendorStatus.TIMEOUT),
        VendorResponse("agy", status=VendorStatus.TIMEOUT),
    ])
    # only one usable vote survived -> below the witness floor -> flag, never the
    # survivor's PASS as "consensus".
    assert out.verdict == ConsensusVerdict.FLAGGED
    assert FlagReason.INSUFFICIENT_WITNESSES in out.reasons
    assert out.n_usable == 1
    assert len(out.abstentions) == 2
    assert {a["status"] for a in out.abstentions} == {"timeout"}


def test_all_vendors_error_is_flagged_not_passed():
    # THE W1 case: every backend errors. Must NOT resolve to a silent pass.
    out = resolve_consensus([
        VendorResponse("claude", status=VendorStatus.ERROR, detail="401"),
        VendorResponse("codex", status=VendorStatus.ERROR, detail="timeout exec"),
    ])
    assert out.verdict == ConsensusVerdict.FLAGGED
    assert FlagReason.NO_USABLE_RESPONSES in out.reasons
    assert out.passed is False
    assert out.n_usable == 0


def test_unavailable_backend_is_abstention():
    out = resolve_consensus([
        _ok("claude", True),
        _ok("codex", True),
        VendorResponse("agy", status=VendorStatus.UNAVAILABLE),
    ])
    # two live independent families still corroborate; the unavailable one is a
    # recorded abstention, not a vote.
    assert out.verdict == ConsensusVerdict.CONSENSUS_PASS
    assert out.n_usable == 2
    assert out.abstentions[0]["vendor"] == "agy"


# --- #1: malformed output is a non-vote ----------------------------------------

def test_malformed_output_excluded_and_can_drop_below_floor():
    out = resolve_consensus([
        _ok("claude", True),
        VendorResponse("codex", status=VendorStatus.MALFORMED, detail="no VERDICT token"),
    ])
    assert out.verdict == ConsensusVerdict.FLAGGED
    assert FlagReason.INSUFFICIENT_WITNESSES in out.reasons
    assert out.n_usable == 1


def test_ok_status_without_passed_is_not_usable():
    # an OK delivery that carries no boolean verdict (passed=None) is not a vote.
    r = VendorResponse("claude", status=VendorStatus.OK, passed=None)
    assert r.is_usable is False


# --- #1/#4: disagreement always flags ------------------------------------------

def test_seeded_disagreement_is_flagged():
    # REGRESSION (Target #4): a planted split — claude PASS, codex FAIL — must FLAG,
    # never be resolved by majority or silently passed.
    out = resolve_consensus([_ok("claude", True), _ok("codex", False)])
    assert out.verdict == ConsensusVerdict.FLAGGED
    assert FlagReason.DISAGREEMENT in out.reasons
    assert out.n_pass == 1 and out.n_fail == 1


def test_majority_pass_with_one_dissent_still_flags():
    # 2 PASS vs 1 FAIL is a real disagreement, not a 66% "pass".
    out = resolve_consensus([_ok("claude", True), _ok("codex", True), _ok("agy", False)])
    assert out.verdict == ConsensusVerdict.FLAGGED
    assert FlagReason.DISAGREEMENT in out.reasons


# --- unanimous FAIL is a decisive corroborated negative, not a flag ------------

def test_unanimous_fail_is_consensus_fail():
    out = resolve_consensus([_ok("claude", False), _ok("codex", False)])
    assert out.verdict == ConsensusVerdict.CONSENSUS_FAIL
    assert out.passed is False
    assert out.flagged is False
    assert out.reasons == []


def test_single_family_unanimous_fail_still_consensus_fail():
    # corroborating a FAIL is the safe direction — the family floor gates PASS only.
    out = resolve_consensus([_ok("claude", False), _ok("claude", False)])
    assert out.verdict == ConsensusVerdict.CONSENSUS_FAIL


# --- #3: required objective witness (two optimists agreeing != a gate) ---------

def test_pass_without_required_objective_witness_flags():
    out = resolve_consensus(
        [_ok("claude", True), _ok("codex", True)],
        require_objective_witness=True,
        objective_witness_present=False,
    )
    assert out.verdict == ConsensusVerdict.FLAGGED
    assert FlagReason.MISSING_OBJECTIVE_WITNESS in out.reasons


def test_pass_with_objective_witness_passes():
    out = resolve_consensus(
        [_ok("claude", True), _ok("codex", True)],
        require_objective_witness=True,
        objective_witness_present=True,
    )
    assert out.verdict == ConsensusVerdict.CONSENSUS_PASS
    assert out.objective_witness_present is True


def test_fail_does_not_need_objective_witness():
    out = resolve_consensus(
        [_ok("claude", False), _ok("codex", False)],
        require_objective_witness=True,
        objective_witness_present=False,
    )
    assert out.verdict == ConsensusVerdict.CONSENSUS_FAIL


# --- #2: numeric tolerance discipline (boundary) -------------------------------

def test_numeric_identical_agrees():
    nc = numeric_consensus([1.234567, 1.234567])
    assert nc.agreement == NumericAgreement.AGREE
    assert nc.near_miss is False


def test_numeric_just_inside_tolerance_is_near_miss_agreement():
    # spread 5e-7 at scale ~1 with rtol 1e-6 -> tol ~1e-6 -> within band.
    nc = numeric_consensus([1.0, 1.0 + 5e-7])
    assert nc.agreement == NumericAgreement.AGREE
    assert nc.near_miss is True
    assert nc.spread <= nc.tolerance


def test_numeric_just_outside_tolerance_disagrees():
    nc = numeric_consensus([1.0, 1.0 + 2e-6])
    assert nc.agreement == NumericAgreement.DISAGREE
    assert nc.spread > nc.tolerance


def test_numeric_boundary_exact_edge_agrees():
    # construct a spread exactly equal to the tolerance -> inclusive '<=' -> AGREE.
    base = 1.0
    tol = DEFAULT_ATOL + DEFAULT_RTOL * base
    nc = numeric_consensus([base, base + tol])
    assert nc.agreement == NumericAgreement.AGREE


def test_numeric_custom_tolerance():
    # a looser rtol turns a would-be disagreement into agreement.
    assert numeric_consensus([1.0, 1.01]).agreement == NumericAgreement.DISAGREE
    assert numeric_consensus([1.0, 1.01], rtol=0.05).agreement == NumericAgreement.AGREE


def test_numeric_nan_is_disagreement():
    nc = numeric_consensus([1.0, float("nan")])
    assert nc.agreement == NumericAgreement.DISAGREE


def test_numeric_single_value_is_unknown():
    nc = numeric_consensus([1.0])
    assert nc.agreement == NumericAgreement.UNKNOWN


# --- numeric integrated into resolve_consensus ---------------------------------

def test_resolve_flags_numeric_disagreement_even_if_bools_agree():
    # both vendors say PASS, but their reported numbers diverge outside tolerance —
    # that is a silent-wrong-number defect; fail closed.
    out = resolve_consensus([
        _ok("claude", True, value=0.42),
        _ok("codex", True, value=0.51),
    ])
    assert out.verdict == ConsensusVerdict.FLAGGED
    assert FlagReason.NUMERIC_DISAGREEMENT in out.reasons
    assert out.numeric.agreement == NumericAgreement.DISAGREE


def test_resolve_passes_on_numeric_near_miss():
    out = resolve_consensus([
        _ok("claude", True, value=0.42),
        _ok("codex", True, value=0.42 + 1e-7),
    ])
    assert out.verdict == ConsensusVerdict.CONSENSUS_PASS
    assert out.numeric.agreement == NumericAgreement.AGREE
    assert out.numeric.near_miss is True


# --- witness binding serialization ---------------------------------------------

def test_outcome_to_dict_is_json_serializable_and_bound():
    out = resolve_consensus([_ok("claude", True, 1.0), _ok("codex", True, 1.0)])
    d = out.to_dict()
    json.dumps(d)  # must not raise
    assert d["verdict"] == "consensus_pass"
    assert d["witnesses"] == ["claude", "codex"]
    assert d["witness_families"] == ["anthropic", "openai"]
    assert d["numeric"]["agreement"] == "agree"


def test_explicit_family_override_used():
    # a vendor may declare its family explicitly (e.g. an unknown engine name).
    r1 = VendorResponse("mystery-a", status=VendorStatus.OK, passed=True, family="anthropic")
    r2 = VendorResponse("mystery-b", status=VendorStatus.OK, passed=True, family="openai")
    out = resolve_consensus([r1, r2])
    assert out.verdict == ConsensusVerdict.CONSENSUS_PASS
    assert set(out.witness_families) == {"anthropic", "openai"}


def test_no_responses_at_all_flags():
    out = resolve_consensus([])
    assert out.verdict == ConsensusVerdict.FLAGGED
    assert FlagReason.NO_USABLE_RESPONSES in out.reasons
