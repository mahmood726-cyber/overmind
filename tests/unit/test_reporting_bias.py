from __future__ import annotations

import pytest

from overmind.evidence.reporting_bias import (
    LINKAGE_BASE_RATE,
    missing_evidence_robme,
    registry_linkage,
    reporting_bias_report,
    outcome_switching_summary,
)


def test_registry_linkage_computes_denominator_and_unpublished():
    r = registry_linkage(n_registered=100, n_published=64, n_in_review=20)
    assert r["linkage_rate"] == 0.64
    assert r["n_unpublished"] == 36
    assert r["unpublished_fraction"] == 0.36
    # 20 included trials at 0.64 linkage project to ~31.2 registered trials
    assert r["projected_registered_denominator"] == 31.2
    assert r["below_base_rate"] is False  # 0.64 ~ base rate 0.636, just above


def test_registry_linkage_flags_below_base_rate():
    r = registry_linkage(n_registered=100, n_published=40)
    assert r["linkage_rate"] == 0.40
    assert r["below_base_rate"] is True  # 0.40 < 0.636


def test_registry_linkage_validates():
    with pytest.raises(ValueError):
        registry_linkage(n_registered=0, n_published=0)
    with pytest.raises(ValueError):
        registry_linkage(n_registered=10, n_published=11)  # published > registered


def test_robme_high_concern_on_low_linkage():
    r = missing_evidence_robme(linkage_rate=0.40, n_unpublished=60)
    assert r["concern_level"] == "high"
    assert any("published" in reason for reason in r["reasons"])
    assert r["is_decision_support"] is True


def test_robme_some_concerns_on_moderate_linkage():
    r = missing_evidence_robme(linkage_rate=0.70, n_unpublished=30)
    assert r["concern_level"] == "some-concerns"


def test_robme_low_when_clean():
    r = missing_evidence_robme(linkage_rate=0.95, n_unpublished=0)
    assert r["concern_level"] == "low"


def test_robme_small_study_signal_escalates():
    # good linkage but funnel asymmetry -> escalates above low
    r = missing_evidence_robme(linkage_rate=0.95, n_unpublished=0, funnel_asymmetry_p=0.02)
    assert r["concern_level"] in ("some-concerns", "high")
    assert any("asymmetry" in reason or "small-study" in reason for reason in r["reasons"])


def test_outcome_switching_summary_carries_base_rate():
    r = outcome_switching_summary(["mortality", "MI", "stroke"], ["mortality", "MI"])
    assert "stroke" in r["dropped_outcomes"]
    assert r["switching_flag"] is True
    assert r["base_rate_reference"] == 0.24


def test_full_report_bundles_signals():
    r = reporting_bias_report(
        n_registered=50, n_published=25, n_in_review=10,
        protocol_outcomes=["a", "b", "c"], reported_outcomes=["a", "b"],
        funnel_asymmetry_p=0.03,
    )
    assert r["capability"] == "reporting_bias_accounting"
    assert r["linkage"]["below_base_rate"] is True  # 0.50 < 0.636
    assert r["rob_me"]["concern_level"] == "high"   # low linkage + asymmetry
    assert "c" in r["outcome_switching"]["dropped_outcomes"]
    assert LINKAGE_BASE_RATE == 0.636
