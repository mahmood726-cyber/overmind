"""Trip-tests for the comparison / both-arms gate (Part VI, 2026-07-14).

A real user reported a live selection error in AMOXICILLIN_AOM: NCT03818815
(OP0201) was pooled as an Augmentin-efficacy trial, but amoxicillin-clavulanate
was BACKGROUND in BOTH arms; the randomised contrast was intranasal OP0201 vs
placebo. Every prior gate (arithmetic, identity, arm-binding) PASSES this — a
human caught what the machine could not. These tests plant that RED case and
prove the new gate BLOCKS it, plus GREEN cases that must still pass.

Each test is fail-before / pass-after in the house style: the pre-fix behaviour
was silent acceptance; the post-fix behaviour is a hard block at the export sink.
"""
from __future__ import annotations

import pytest

from overmind.gates.contract import Claim, SourceTier
from overmind.gates.channel import ExportChannel, ChannelViolation
from overmind.gates.comparison_gate import (
    guard_comparison, ComparisonError, evaluate,
)
from overmind.gates.resolver import LocatorResolver, Resolution


# Stub resolver: resolves any NCT#om locator to a benign ground truth so the
# comparison gate (step 6) is what decides accept/block, not resolution.
class _StubResolver(LocatorResolver):
    def __init__(self):
        super().__init__(aact_path=None)

    def resolve(self, locator, claimed_value=None):
        return Resolution(True, True, "stub",
                          ground_truth={"value": claimed_value, "title": "Treatment failure",
                                        "group": None, "arm": None,
                                        "timepoint": "day 12", "unit": "participants"})


def _chan():
    return ExportChannel(resolver=_StubResolver())


# ---- unit level: evaluate() gets the class right ---------------------------

def test_evaluate_op0201_is_wrong_comparison():
    wrong, reason = evaluate("amoxicillin",
        ["Drug: OP0201 + Antibiotics", "Placebo Comparator: Placebo +Antibiotics"])
    assert wrong is True
    assert "op0201" in reason.lower()


def test_evaluate_adalimumab_dose_both_arms_is_wrong():
    wrong, _ = evaluate("adalimumab",
        ["Adalimumab + Low Dose Methotrexate", "Adalimumab + High Dose Methotrexate"])
    assert wrong is True


def test_evaluate_normal_addon_design_is_ok():
    # abatacept is the contrast; methotrexate is legit background in both arms
    wrong, _ = evaluate("abatacept",
        ["Abatacept + Methotrexate", "Placebo + Methotrexate"])
    assert wrong is False


def test_evaluate_crossover_is_ok():
    wrong, _ = evaluate("elamipretide",
        ["Elamipretide, Then Placebo", "Placebo, Then Elamipretide"])
    assert wrong is False


def test_evaluate_drug_vs_placebo_is_ok():
    wrong, _ = evaluate("amoxicillin",
        ["Amoxicillin-clavulanate", "Placebo"])
    assert wrong is False


# ---- gate level: guard_comparison raises / passes -------------------------

def _claim(drug, arms):
    return Claim("treatment failure", 30, SourceTier.REGISTRY, "NCT03818815#om[3]",
                 meta={"drug_of_interest": drug, "trial_arms": arms,
                       "outcome": "Treatment failure", "timepoint": "day 12",
                       "unit": "participants"})


def test_guard_blocks_op0201():
    with pytest.raises(ComparisonError, match="wrong comparison"):
        guard_comparison(_claim("amoxicillin",
            ["Drug: OP0201 + Antibiotics", "Placebo Comparator: Placebo +Antibiotics"]))


def test_guard_fails_closed_when_arms_missing():
    """Declaring a drug of interest but omitting arms is refused — no bypass by
    omission (the failure mode agy flagged for every gate)."""
    c = Claim("treatment failure", 30, SourceTier.REGISTRY, "NCT03818815#om[3]",
              meta={"drug_of_interest": "amoxicillin"})
    with pytest.raises(ComparisonError, match="comparison-UNVERIFIED"):
        guard_comparison(c)


def test_guard_passes_real_augmentin_trial():
    guard_comparison(_claim("amoxicillin", ["Amoxicillin-clavulanate", "Placebo"]))  # no raise


def test_guard_noop_when_no_drug_declared():
    """A claim that does not declare a drug of interest is unaffected — backward
    compatible with every existing lane."""
    guard_comparison(Claim("x", 1, SourceTier.REGISTRY, "NCT1#om[1]", meta={}))  # no raise


# ---- full channel: the block happens at the export sink --------------------

def test_channel_blocks_op0201_end_to_end():
    """RED -> the OP0201 datum cannot leave the channel."""
    bad = _claim("amoxicillin",
        ["Drug: OP0201 + Antibiotics", "Placebo Comparator: Placebo +Antibiotics"])
    with pytest.raises(ChannelViolation, match="wrong comparison"):
        _chan().emit(bad)


def test_channel_emits_corrected_augmentin_datum():
    """GREEN -> after excluding OP0201, Hoberman's real amox-clav-vs-placebo datum
    emits cleanly (proving the gate blocks the wrong trial, not the right one)."""
    good = Claim("treatment failure", 23, SourceTier.REGISTRY, "NCT00377260#om[1]",
                 meta={"drug_of_interest": "amoxicillin",
                       "trial_arms": ["Amoxicillin-clavulanate", "Placebo"],
                       "outcome": "Treatment failure", "timepoint": "day 12",
                       "unit": "participants"})
    r = _chan().emit(good)
    assert "comparison" in r.passed_gates
    assert r.seal_valid
