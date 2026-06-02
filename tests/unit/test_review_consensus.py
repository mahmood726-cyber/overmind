"""Tests for multi-reviewer signed consensus (#4)."""
from __future__ import annotations

import json

from overmind.review.consensus import attest, compute_consensus, load_reviews


def _write(d, name, decisions):
    (d / f"{name}.jsonl").write_text(
        "\n".join(json.dumps({"item_id": i, "decision": v}) for i, v in decisions.items()),
        encoding="utf-8",
    )


def test_agreement_conflict_and_consensus(tmp_path):
    _write(tmp_path, "alice", {"p1": "include", "p2": "exclude", "p3": "include"})
    _write(tmp_path, "bob",   {"p1": "include", "p2": "include", "p3": "include"})
    reviews = load_reviews(tmp_path)
    c = compute_consensus(reviews)
    assert set(c["reviewers"]) == {"alice", "bob"}
    assert c["items_complete"] == 3
    assert "p2" in c["conflicts"]          # include vs exclude → conflict
    assert "p1" not in c["conflicts"]
    assert c["consensus"]["p1"] == "include"
    assert c["percent_agreement"] == round(2 / 3, 4)   # p1,p3 agree; p2 differs
    assert c["kappa_method"] == "cohen"
    assert c["kappa"] is not None


def test_fleiss_for_three_reviewers(tmp_path):
    for name in ("a", "b", "cc"):
        _write(tmp_path, name, {"p1": "include", "p2": "exclude"})
    c = compute_consensus(load_reviews(tmp_path))
    assert c["kappa_method"] == "fleiss"
    assert c["percent_agreement"] == 1.0   # all unanimous per item


def test_attestations_present(tmp_path):
    _write(tmp_path, "alice", {"p1": "include"})
    reviews = load_reviews(tmp_path)
    a = attest(reviews, compute_consensus(reviews))
    assert "alice" in a["reviewer_attestations"]
    att = a["reviewer_attestations"]["alice"]
    assert "sha256" in att and "method" in att and "signed" in att  # signed True only if a signer is configured
    assert "consensus_attestation" in a
