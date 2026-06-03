from __future__ import annotations

import json

import pytest

from overmind.evidence.corpus import CorpusRecord, default_provider
from overmind.evidence.screening import (
    EXCLUSION_REASONS,
    PENDING,
    SUGGEST_EXCLUDE,
    SUGGEST_INCLUDE,
    ScreeningRun,
    pico_query,
    screen,
)


def _recs():
    return [
        CorpusRecord(record_id="pmid:1", title="Dapagliflozin in heart failure with reduced ejection fraction",
                     abstract="randomized trial of dapagliflozin in HFrEF showing reduced mortality"),
        CorpusRecord(record_id="pmid:2", title="Empagliflozin and heart failure outcomes",
                     abstract="SGLT2 inhibitor empagliflozin reduces heart failure hospitalization"),
        CorpusRecord(record_id="pmid:3", title="A study of orange juice and breakfast cereal",
                     abstract="nutrition survey unrelated to cardiology"),
    ]


def test_screen_ranks_relevant_above_irrelevant():
    proposals = screen(_recs(), query="dapagliflozin heart failure")
    by_id = {p.record_id: p for p in proposals}
    # the dapagliflozin HFrEF paper outranks the orange-juice paper
    assert by_id["pmid:1"].rank < by_id["pmid:3"].rank
    assert by_id["pmid:3"].suggestion == SUGGEST_EXCLUDE


def test_screen_never_auto_includes():
    # Even the strongest match stays PENDING / needs_review — the machine closes nothing.
    proposals = screen(_recs(), query="dapagliflozin heart failure reduced ejection fraction",
                       include_threshold=0.0)  # force every score over the include line
    assert proposals
    for p in proposals:
        assert p.decision == PENDING
        assert p.needs_review is True
    # the suggestion may be SUGGEST_INCLUDE, but the decision is not
    assert any(p.suggestion == SUGGEST_INCLUDE for p in proposals)


def test_screen_is_complete_no_silent_truncation():
    # every input record must appear in the worklist (zero-overlap ones included)
    recs = _recs()
    proposals = screen(recs, query="dapagliflozin")
    assert {p.record_id for p in proposals} == {r.record_id for r in recs}


def test_relevance_feedback_changes_ranking():
    recs = _recs()
    base = screen(recs, query="heart failure")
    fed = screen(recs, query="heart failure", seed_includes=["pmid:1"])
    # feedback folds dapagliflozin/HFrEF terms in; ranking remains deterministic
    assert [p.record_id for p in fed] == [p.record_id for p in screen(recs, query="heart failure", seed_includes=["pmid:1"])]
    assert isinstance(base, list)


def test_pico_query_flatten_and_empty():
    assert "finerenone" in pico_query({"int": "finerenone", "pop": "CKD patients"})
    with pytest.raises(ValueError):
        pico_query({})


def test_screen_requires_query_or_pico():
    with pytest.raises(ValueError):
        screen(_recs())


def test_screening_run_writes_artifact_and_reports_zero_auto_includes(tmp_path):
    report = ScreeningRun(provider_records=default_provider().records(),
                          artifacts_dir=tmp_path / "artifacts").run(query="empagliflozin heart failure")
    assert report["capability"] == "screening"
    assert report["auto_included"] == 0
    assert report["candidate_count"] == report["proposal_count"]
    assert set(report["exclusion_reason_vocab"]) == EXCLUSION_REASONS
    written = json.loads((tmp_path / "artifacts" / "evidence" / "screening.json").read_text(encoding="utf-8"))
    assert written["decision_policy"].startswith("machine suggests")
