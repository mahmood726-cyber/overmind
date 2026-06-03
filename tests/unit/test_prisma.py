from __future__ import annotations

import json

from overmind.evidence.prisma import outcome_switching, prisma_flow


def test_prisma_flow_counts_and_awaiting():
    records = [
        {"record_id": "1", "duplicate": True},  # removed before screening
        {"record_id": "2", "ta_decision": "exclude", "ta_reason": "wrong_design"},
        {"record_id": "3", "ta_decision": "exclude", "ta_reason": "wrong_population"},
        {"record_id": "4", "ta_decision": "include", "ft_decision": "include"},
        {"record_id": "5", "ta_decision": "include", "ft_decision": "exclude", "ft_reason": "no_outcome_data"},
        {"record_id": "6", "ta_decision": "include"},  # awaiting full-text decision
        {"record_id": "7", "ta_decision": "include", "retrieved": False},  # not retrieved
    ]
    r = prisma_flow(records)
    assert r["identification"]["records_identified"] == 7
    assert r["identification"]["duplicates_removed"] == 1
    assert r["screening"]["records_screened"] == 6
    assert r["screening"]["records_excluded_title_abstract"] == 2
    assert r["screening"]["ta_exclusion_reasons"] == {"wrong_design": 1, "wrong_population": 1}
    assert r["screening"]["reports_sought"] == 4
    assert r["screening"]["reports_not_retrieved"] == 1
    assert r["screening"]["reports_assessed_eligibility"] == 2
    assert r["screening"]["reports_excluded_full_text"] == 1
    assert r["screening"]["awaiting_assessment"] == 1
    assert r["included"]["studies_included"] == 1


def test_prisma_never_counts_undecided_as_included():
    # a TA-included record with no full-text decision must NOT be counted included
    r = prisma_flow([{"record_id": "x", "ta_decision": "include"}])
    assert r["included"]["studies_included"] == 0
    assert r["screening"]["awaiting_assessment"] == 1


def test_prisma_writes_artifact(tmp_path):
    prisma_flow([{"record_id": "x", "ta_decision": "include", "ft_decision": "include"}],
                artifacts_dir=tmp_path / "artifacts")
    written = json.loads((tmp_path / "artifacts" / "evidence" / "prisma.json").read_text(encoding="utf-8"))
    assert written["standard"] == "PRISMA 2020"


def test_outcome_switching_detects_dropped():
    r = outcome_switching(
        protocol_outcomes=["CV death", "HF hospitalization", "All-cause mortality"],
        reported_outcomes=["CV death", "HF hospitalization", "eGFR slope"],  # mortality dropped, eGFR added
    )
    assert r["dropped_outcomes"] == ["All-cause mortality"]
    assert r["added_outcomes"] == ["eGFR slope"]
    assert r["switching_flag"] is True
    assert r["dropped_fraction"] == round(1 / 3, 4)


def test_outcome_switching_clean_when_matching():
    r = outcome_switching(["A", "B"], ["b", "a"])  # case/space-insensitive match
    assert r["dropped_outcomes"] == []
    assert r["switching_flag"] is False
    assert r["dropped_fraction"] == 0.0


def test_outcome_switching_empty_protocol_ratio_none():
    r = outcome_switching([], ["A"])
    assert r["dropped_fraction"] is None
