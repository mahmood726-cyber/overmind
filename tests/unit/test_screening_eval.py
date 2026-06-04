from __future__ import annotations

import pytest

from overmind.evidence.corpus import CorpusRecord
from overmind.evidence.screening_eval import SAFETY_BAR, screening_recall


def _recs(specs):
    return [CorpusRecord(record_id=i, title=t, abstract=a) for i, t, a in specs]


def test_recall_is_one_when_all_gold_includes_are_surfaced():
    recs = _recs([
        ("inc1", "Dapagliflozin in heart failure", "SGLT2 inhibitor heart failure trial"),
        ("inc2", "Empagliflozin heart failure outcomes", "SGLT2 inhibitor reduced heart failure"),
        ("exc1", "Orange juice and cereal", "unrelated nutrition survey"),
        ("exc2", "Medieval trade routes", "history of Mediterranean shipping"),
    ])
    rep = screening_recall(recs, ["inc1", "inc2"], query="SGLT2 inhibitor heart failure")
    assert rep["review_bucket"]["recall"] == 1.0
    assert rep["meets_safety_bar"] is True
    assert rep["missed_gold_includes"] == []
    assert rep["safety_bar"] == SAFETY_BAR


def test_recall_drops_when_an_include_has_no_query_overlap():
    # a true include phrased with NO query vocabulary lands in SUGGEST_EXCLUDE (zero
    # lexical overlap) -> not in the review bucket -> recall < 1, and it is reported
    # as a missed gold include. Proves the metric is real, not vacuously 1.0.
    recs = _recs([
        ("inc1", "Dapagliflozin in heart failure", "SGLT2 inhibitor heart failure trial"),
        ("inc2", "Sodium glucose cotransporter study", "xyzzy quux foobar baz qux"),  # no overlap
        ("exc1", "Orange juice and cereal", "unrelated nutrition survey"),
    ])
    rep = screening_recall(recs, ["inc1", "inc2"], query="SGLT2 inhibitor heart failure")
    assert rep["review_bucket"]["recall"] < 1.0
    assert "inc2" in rep["missed_gold_includes"]
    assert rep["meets_safety_bar"] is False  # 0.5 < 0.95


def test_empty_gold_fails_closed():
    recs = _recs([("a", "x", "y")])
    with pytest.raises(ValueError):
        screening_recall(recs, [], query="x")


def test_reports_workload_fraction():
    recs = _recs([
        ("inc1", "Dapagliflozin heart failure", "SGLT2 inhibitor heart failure"),
        ("exc1", "geology of sandstone", "desert basins"),
        ("exc2", "satellite image segmentation", "neural networks remote sensing"),
        ("exc3", "medieval trade", "Mediterranean shipping"),
    ])
    rep = screening_recall(recs, ["inc1"], query="SGLT2 inhibitor heart failure")
    # 1 of 4 records in the review bucket -> 0.25 workload
    assert rep["review_bucket"]["workload_fraction"] == 0.25
    assert rep["review_bucket"]["recall"] == 1.0
