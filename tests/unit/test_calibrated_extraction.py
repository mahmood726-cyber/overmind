"""Tests for the calibrated-extraction seam (quorum + conformal + provenance)
and the two deterministic field parsers that feed it.

The deterministic pooling/validation core is not touched by any of this; these
tests lock the additive layer's behaviour and prove the conformal mechanism
engages on a noisy base extractor.
"""
from __future__ import annotations

import pytest

from overmind.evidence.calibrated_extraction import (
    CalibrationExample,
    CellState,
    ConformalAbstainer,
    ExtractedValue,
    adjudicate_cell,
    adjudicate_record,
    calibrate_thresholds,
    values_agree,
)
from overmind.evidence.field_parsers import parse_labeled, parse_proximity


# --------------------------------------------------------------------------- #
# ExtractedValue / values_agree
# --------------------------------------------------------------------------- #
def test_confidence_bounds_enforced():
    with pytest.raises(ValueError):
        ExtractedValue(0.8, confidence=1.5)
    with pytest.raises(ValueError):
        ExtractedValue(0.8, confidence=-0.1)


def test_values_agree_ratio_log_scale():
    # ratios compare on the log scale; 0.80 vs 0.82 agree within 5% log tol
    assert values_agree(0.80, 0.82, "HR", rel_tol=0.05)
    # 0.5 vs 2.0 are a factor of 4 apart -> disagree
    assert not values_agree(0.5, 2.0, "RR")


def test_values_agree_none_semantics():
    assert values_agree(None, None, "ratio")      # shared "not present"
    assert not values_agree(None, 0.8, "ratio")    # one present, one not
    assert not values_agree(0.8, None, "ratio")


def test_values_agree_categorical():
    assert values_agree("RR", "rr", "measure_type")
    assert not values_agree("RR", "HR", "measure_type")


# --------------------------------------------------------------------------- #
# adjudicate_cell — the four states
# --------------------------------------------------------------------------- #
def test_adjudicate_accept():
    v = adjudicate_cell("HR", ExtractedValue(0.80, 0.9), ExtractedValue(0.81, 0.9))
    assert v.state is CellState.ACCEPT
    assert v.accepted and not v.needs_review
    assert abs(v.value - 0.80) < 1e-9


def test_adjudicate_flag_on_disagree():
    v = adjudicate_cell("HR", ExtractedValue(0.5, 0.9), ExtractedValue(2.0, 0.9))
    assert v.state is CellState.FLAG_DISAGREE
    assert v.needs_review and v.value is None


def test_adjudicate_abstain_on_shared_none():
    v = adjudicate_cell("HR", ExtractedValue(None, 0.0), ExtractedValue(None, 0.0))
    assert v.state is CellState.ABSTAIN_LOWCONF
    assert v.abstained and v.value is None


def test_adjudicate_abstain_on_low_confidence():
    v = adjudicate_cell("HR", ExtractedValue(0.8, 0.5), ExtractedValue(0.8, 0.5), threshold=0.7)
    assert v.state is CellState.ABSTAIN_LOWCONF
    assert v.value is None


def test_adjudicate_both_wrong_on_structural_check():
    # both models agree on a NEGATIVE ratio -> impossible; independent check rejects
    v = adjudicate_cell("RR", ExtractedValue(-0.5, 0.9), ExtractedValue(-0.5, 0.9),
                        structural_check=lambda x: x > 0)
    assert v.state is CellState.BOTH_WRONG
    assert v.needs_review and v.value is None


def test_both_wrong_takes_precedence_over_low_conf():
    # a failing structural check is reported even if confidence is also low
    v = adjudicate_cell("RR", ExtractedValue(-0.5, 0.1), ExtractedValue(-0.5, 0.1),
                        threshold=0.9, structural_check=lambda x: x > 0)
    assert v.state is CellState.BOTH_WRONG


def test_structural_check_that_raises_is_a_reject():
    def boom(_x):
        raise RuntimeError("bad")
    v = adjudicate_cell("RR", ExtractedValue(0.8, 0.9), ExtractedValue(0.8, 0.9),
                        structural_check=boom)
    assert v.state is CellState.BOTH_WRONG


# --------------------------------------------------------------------------- #
# Conformal calibration — coverage guarantee + mechanism engages
# --------------------------------------------------------------------------- #
def test_calibrate_thresholds_rejects_bad_alpha():
    with pytest.raises(ValueError):
        calibrate_thresholds([], alpha=0.0)
    with pytest.raises(ValueError):
        calibrate_thresholds([], alpha=1.0)


def test_conformal_coverage_guarantee_and_engages_on_noisy_base():
    # Synthetic noisy extractor: correct cells tend high-confidence, wrong cells
    # low-confidence, but with overlap. Calibrate on half, measure on the other.
    import random
    rng = random.Random(0)
    def make(n):
        out = []
        for _ in range(n):
            correct = rng.random() < 0.7
            # correct: conf ~ U(0.5,1.0); wrong: conf ~ U(0.0,0.6)  (overlap)
            conf = rng.uniform(0.5, 1.0) if correct else rng.uniform(0.0, 0.6)
            out.append(CalibrationExample("ratio", conf, correct))
        return out
    cal, test = make(400), make(400)

    th = calibrate_thresholds(cal, alpha=0.1)
    rep = ConformalAbstainer(th).report(test)
    # Coverage guarantee: retains ~>= 1-alpha of true cells (allow MC slack).
    assert rep["coverage"] >= 0.85
    # The layer actually engages on a noisy base: it rejects a non-trivial share
    # and drives accepted-error below the raw error rate.
    assert rep["rejection_rate"] > 0.05
    raw_error = sum(1 for e in test if not e.correct) / len(test)
    assert rep["accepted_error"] < raw_error


def test_conformal_abstainer_default_tau_fallback():
    ab = ConformalAbstainer({"__default__": 0.6})
    assert ab.tau_for("unseen_field") == 0.6
    assert ab.accept("unseen_field", 0.7)
    assert not ab.accept("unseen_field", 0.5)


# --------------------------------------------------------------------------- #
# Record-level rollup
# --------------------------------------------------------------------------- #
def test_adjudicate_record_rollup():
    fields = {
        "value": (ExtractedValue(0.8, 0.9), ExtractedValue(0.81, 0.9)),      # accept
        "measure_type": (ExtractedValue("HR", 0.9), ExtractedValue("RR", 0.9)),  # flag
        "n": (ExtractedValue(None, 0.0), ExtractedValue(None, 0.0)),          # abstain
    }
    r = adjudicate_record(fields)
    assert set(r["accepted"]) == {"value"}
    assert r["flagged"] == ["measure_type"]
    assert r["abstained"] == ["n"]
    assert r["needs_review"] is True


# --------------------------------------------------------------------------- #
# Field parsers
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text,mtype,val", [
    ("RR: 0.87", "RR", 0.87),
    ("HR, 2.00; 95% CI, 1.41-2.83", "HR", 2.00),
    ("The hazard ratio was 0.85 (95% CI 0.78-0.93)", "HR", 0.85),
    ("odds ratio of 1.2", "OR", 1.2),
])
def test_parsers_agree_and_accept_on_clean(text, mtype, val):
    va, ta = parse_labeled(text)
    vb, tb = parse_proximity(text)
    v = adjudicate_cell("ratio", va, vb)
    t = adjudicate_cell("measure_type", ta, tb)
    assert v.state is CellState.ACCEPT and abs(v.value - val) < 1e-6
    assert t.state is CellState.ACCEPT and t.value == mtype


@pytest.mark.parametrize("text", [
    "The hazard ratio was not calculable due to insufficient events.",  # negation
    "The study enrolled 450 patients with a mean age of 65 years.",     # no measure token
])
def test_parsers_abstain_on_no_value_text(text):
    va, _ = parse_labeled(text)
    vb, _ = parse_proximity(text)
    v = adjudicate_cell("ratio", va, vb)
    assert v.value is None  # abstained or flagged — never a fabricated value


def test_parsers_abstain_on_ambiguous_multivalue():
    # two different labelled estimates -> the correct action is to abstain
    text = "Risk ratio estimates varied: RR 0.9 in ITT, RR 0.85 in PP analysis."
    va, _ = parse_labeled(text)
    vb, _ = parse_proximity(text)
    v = adjudicate_cell("ratio", va, vb)
    assert v.value is None


def test_parser_rejects_count_as_effect():
    # a raw count adjacent to a measure token must not be read as an effect ratio
    va, _ = parse_labeled("HR analysis included n = 450 patients")
    vb, _ = parse_proximity("HR analysis included n = 450 patients")
    v = adjudicate_cell("ratio", va, vb)
    assert v.value is None
