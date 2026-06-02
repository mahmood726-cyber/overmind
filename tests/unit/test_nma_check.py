"""Tests for the NMA assumption-checker (#5)."""
from __future__ import annotations

from overmind.intelligence.nma_check import check_nma


def _spec(**kw):
    base = {
        "treatments": ["A", "B", "C"],
        "comparisons": [
            {"t1": "A", "t2": "B", "k": 5, "I2": 30},
            {"t1": "B", "t2": "C", "k": 4, "I2": 20},
        ],
        "consistency": {"method": "design-by-treatment", "p": 0.41},
        "sucra": {"A": 0.8, "B": 0.5, "C": 0.2},
        "ranking_uncertainty_reported": True,
    }
    base.update(kw)
    return base


def test_clean_network_ok():
    r = check_nma(_spec())
    assert r["status"] == "ok"
    assert r["errors"] == 0 and r["warnings"] == 0


def test_disconnected_network_errors():
    # D has no comparison → isolated
    r = check_nma(_spec(treatments=["A", "B", "C", "D"]))
    assert r["status"] == "fail"
    assert any(f["check"] == "network_connected" for f in r["findings"])


def test_inconsistency_flagged():
    r = check_nma(_spec(consistency={"method": "node-split", "p": 0.01}))
    assert any(f["check"] == "consistency_violated" and f["severity"] == "error" for f in r["findings"])


def test_missing_consistency_warns():
    r = check_nma(_spec(consistency=None))
    assert any(f["check"] == "consistency_assessed" and f["severity"] == "warn" for f in r["findings"])


def test_sucra_without_uncertainty_warns():
    r = check_nma(_spec(ranking_uncertainty_reported=False))
    assert any(f["check"] == "sucra_without_uncertainty" for f in r["findings"])


def test_single_study_comparison_warns():
    r = check_nma(_spec(comparisons=[
        {"t1": "A", "t2": "B", "k": 1, "I2": 0},
        {"t1": "B", "t2": "C", "k": 4, "I2": 10},
    ]))
    assert any(f["check"] == "single_study_comparisons" for f in r["findings"])


def test_too_few_treatments_errors():
    r = check_nma(_spec(treatments=["A", "B"],
                        comparisons=[{"t1": "A", "t2": "B", "k": 5, "I2": 10}]))
    assert any(f["check"] == "min_treatments" for f in r["findings"])
