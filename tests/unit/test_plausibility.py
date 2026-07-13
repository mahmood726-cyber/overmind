"""Deterministic plausibility-gate trip-tests (external consistency).

Each rule has a test that TRIPS it with an impossible number, plus a companion that
a plausible number passes. The headline case is the DTA70 signature — a sensitivity
range of 0.046 across 17 studies — caught with NO model, NO network.
"""
from __future__ import annotations

import pytest

from overmind.factstore import (
    FactStore, check_plausibility, Provenance,
    ImplausibleFactError,
)


# --- the DTA70 signature: impossible dispersion ---------------------------------

def test_dta70_impossible_dispersion_is_flagged():
    """TRIP TEST: Se 0.858 across k=17 with a 0.046 spread is impossible. Caught."""
    r = check_plausibility(
        {"metric": "sensitivity", "sensitivity": 0.858, "k": 17, "range": 0.046})
    assert r.ok is False
    assert any("impossible dispersion" in v for v in r.violations)


def test_wide_dispersion_passes():
    r = check_plausibility({"metric": "sensitivity", "k": 17, "range": 0.35})
    assert r.ok is True


def test_dispersion_needs_enough_studies():
    # a tight range across FEW studies is not implausible (small k -> agreement happens)
    r = check_plausibility({"metric": "sensitivity", "k": 3, "range": 0.02})
    assert r.ok is True


# --- out of range ---------------------------------------------------------------

def test_proportion_out_of_range_flagged():
    assert check_plausibility({"sensitivity": 1.4}).ok is False
    assert check_plausibility({"specificity": -0.1}).ok is False
    assert check_plausibility(1.2, kind="sensitivity").ok is False


def test_i2_and_tau2_out_of_range():
    assert check_plausibility({"i2": 140}).ok is False
    assert check_plausibility({"tau2": -0.3}).ok is False
    assert check_plausibility({"i2": 62, "tau2": 0.11}).ok is True


# --- effect ratio bounds (the HR 8.6 caught-by-luck case) -----------------------

def test_impossible_and_extreme_effects():
    assert check_plausibility({"hr": 0.0}).ok is False        # <= 0 impossible (HARD)
    assert check_plausibility({"hr": -1.2}).ok is False
    assert check_plausibility({"hr": 500.0}).ok is False      # astronomical (HARD)
    # HR 8.6 is extreme-but-possible: a soft WARNING (surfaced), not a hard block
    r = check_plausibility({"hr": 8.6})
    assert r.ok is True and any("extreme ratio" in x for x in r.warnings)
    assert check_plausibility({"or": 1.3}).ok is True         # ordinary effect passes
    assert check_plausibility({"or": 1.3}).warnings == []


# --- CI must contain its own point (the 1.53 [1.03-1.08] bug) -------------------

def test_ci_not_containing_point_flagged():
    r = check_plausibility({"point": 1.53, "ci_low": 1.03, "ci_high": 1.08})
    assert r.ok is False
    assert any("outside its own CI" in v for v in r.violations)


def test_inverted_ci_flagged():
    assert check_plausibility({"ci_low": 1.2, "ci_high": 0.8}).ok is False


def test_valid_ci_passes():
    assert check_plausibility({"point": 0.72, "ci_low": 0.55, "ci_high": 0.95}).ok is True


# --- 2x2 that doesn't sum to N --------------------------------------------------

def test_twobytwo_sum_mismatch_flagged():
    assert check_plausibility({"a": 10, "b": 20, "c": 30, "d": 40, "n": 200}).ok is False
    assert check_plausibility({"a": 10, "b": 20, "c": 30, "d": 40, "n": 100}).ok is True


# --- counts vs reported effect (the 57/249 RapidMeta class) ---------------------

def test_counts_contradict_reported_rr():
    # 10/100 vs 20/100 => RR 0.5, but the fact claims RR 2.0
    r = check_plausibility({"events_t": 10, "n_t": 100, "events_c": 20, "n_c": 100, "rr": 2.0})
    assert r.ok is False
    assert any("contradicts counts" in v for v in r.violations)


def test_counts_consistent_with_rr_passes():
    r = check_plausibility({"events_t": 10, "n_t": 100, "events_c": 20, "n_c": 100, "rr": 0.5})
    assert r.ok is True


# --- zero-variance pool ---------------------------------------------------------

def test_zero_variance_pool_flagged():
    assert check_plausibility({"effect": 0.7, "se": 0.0}).ok is False
    assert check_plausibility({"point": 0.7, "ci_low": 0.7, "ci_high": 0.7}).ok is False


# --- INTEGRATION: an implausible fact can never be verified or consumed ----------

def test_implausible_fact_cannot_be_verified_or_consumed():
    """TRIP TEST end-to-end: even a REAL-provenance fact that is numerically
    impossible (the DTA70 shape) is FLAGGED and cannot be verified -> cannot be
    consumed. External consistency gates independently of provenance."""
    fs = FactStore()
    fid = fs.record_real(
        "TB.DTA.sensitivity", {"metric": "sensitivity", "sensitivity": 0.858, "k": 17, "range": 0.046},
        source="reconstructed", lane="dta-lane")
    with pytest.raises(ImplausibleFactError):
        fs.verify(fid, families=["openai", "google"])
    # flagged on the fact, not silently dropped
    assert any(e["kind"] == "implausible" for e in fs.get(fid).events)
    # and unconsumable (never reached verified)
    from overmind.factstore import UnverifiedFactError
    with pytest.raises(UnverifiedFactError):
        fs.consume_verified("TB.DTA.sensitivity")


def test_plausible_real_fact_still_verifies_and_consumes():
    fs = FactStore()
    fid = fs.record_real("m.effect", {"rr": 0.63, "ci_low": 0.5, "ci_high": 0.8, "point": 0.63},
                         source="PMID:1", lane="l")
    fs.verify(fid, families=["openai", "google"])
    assert fs.consume_verified("m.effect")["rr"] == 0.63
