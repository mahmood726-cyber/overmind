from __future__ import annotations

import json

import pytest

from overmind.evidence.extraction import (
    ExtractionError,
    extract_and_validate,
    js_escape,
    validate_trial,
)


def _good_binary_trial():
    return {
        "nct": "NCT01035255", "name": "DAPA-HF", "source": "reference", "verified": True,
        "allOutcomes": [{"shortLabel": "CV death/HF hosp", "estimandType": "HR",
                          "tE": 386, "tN": 2373, "cE": 502, "cN": 2371}],
        "rob": ["low", "low", "low", "low", "some-concerns"],
    }


# --- HARD violations raise (and never substitute defaults) ----------------

def test_missing_identifier_raises():
    with pytest.raises(ExtractionError, match="identifier"):
        validate_trial({"name": "X", "allOutcomes": [{"md": 1, "se": 1}]})


def test_missing_name_raises_no_default():
    with pytest.raises(ExtractionError, match="name"):
        validate_trial({"nct": "NCT1", "allOutcomes": [{"md": 1, "se": 1}]})


def test_no_outcomes_raises():
    with pytest.raises(ExtractionError, match="no outcomes"):
        validate_trial({"nct": "NCT1", "name": "X", "allOutcomes": []})


def test_outcome_without_usable_data_raises():
    with pytest.raises(ExtractionError, match="no usable"):
        validate_trial({"nct": "NCT1", "name": "X", "allOutcomes": [{"shortLabel": "y"}]})


def test_bad_estimand_type_raises():
    with pytest.raises(ExtractionError, match="estimandType"):
        validate_trial({"nct": "NCT1", "name": "X",
                        "allOutcomes": [{"estimandType": "XR", "md": 1, "se": 1}]})


def test_bad_rob_length_raises():
    t = _good_binary_trial()
    t["rob"] = ["low", "low"]
    with pytest.raises(ExtractionError, match="5-element"):
        validate_trial(t)


def test_bad_rob_level_raises():
    t = _good_binary_trial()
    t["rob"] = ["low", "low", "low", "low", "terrible"]
    with pytest.raises(ExtractionError, match="invalid level"):
        validate_trial(t)


# --- SOFT issues flag needsReview (do not raise) --------------------------

def test_ci_not_ordered_flags_review():
    v = validate_trial({"nct": "N", "name": "X",
                        "allOutcomes": [{"estimandType": "HR", "effect": 0.8, "lci": 0.9, "uci": 1.1}]})
    assert v["needsReview"] is True
    assert any("CI not ordered" in m for m in v["_issues"])


def test_inverted_hr_vs_counts_flags_review():
    # publishedHR points one way (>1) but the 2x2 counts imply OR < 1
    v = validate_trial({"nct": "N", "name": "X", "allOutcomes": [{
        "estimandType": "HR", "publishedHR": 7.08, "hrLCI": 5.0, "hrUCI": 9.0,
        "tE": 10, "tN": 100, "cE": 40, "cN": 100,
    }]})
    assert v["needsReview"] is True
    assert any("contradicts count-derived OR" in m for m in v["_issues"])


def test_negative_se_flags_review():
    v = validate_trial({"nct": "N", "name": "X",
                        "allOutcomes": [{"estimandType": "MD", "md": 3.0, "se": -1.0}]})
    assert any("standard error" in m for m in v["_issues"])


def test_clean_trial_passes_without_review():
    v = validate_trial(_good_binary_trial())
    assert v["needsReview"] is False
    assert v["_issues"] == []
    assert v["id"] == "NCT01035255"


def test_auto_extracted_always_needs_review():
    v = validate_trial(_good_binary_trial(), auto_extracted=True)
    assert v["needsReview"] is True


# --- batch + artifact -----------------------------------------------------

def test_batch_collects_rejects_without_aborting(tmp_path):
    trials = [_good_binary_trial(), {"name": "no-id", "allOutcomes": [{"md": 1, "se": 1}]}]
    report = extract_and_validate(trials, artifacts_dir=tmp_path / "artifacts")
    assert report["validated_count"] == 1
    assert report["rejected_count"] == 1
    written = json.loads((tmp_path / "artifacts" / "evidence" / "extraction.json").read_text(encoding="utf-8"))
    assert written["capability"] == "data_extraction"
    assert "fail_closed_policy" in written


# --- js_escape (the RapidMeta apostrophe bug) -----------------------------

def test_js_escape_neutralizes_apostrophe():
    assert js_escape("the trial's primary outcome") == "the trial\\'s primary outcome"
    assert js_escape("a\\b") == "a\\\\b"
