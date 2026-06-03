from __future__ import annotations

import json

from overmind.evidence.corpus import CorpusRecord, default_provider
from overmind.evidence.grounding import extract_identifiers, ground_claims


def _recs():
    return [
        CorpusRecord(record_id="pmid:31535829", title="Dapagliflozin in HFrEF",
                     pmid="31535829", doi="10.1056/NEJMoa1911303"),
        CorpusRecord(record_id="pmid:32865377", title="Empagliflozin in HF",
                     pmid="32865377", doi="10.1056/NEJMoa2022190"),
    ]


def test_extract_identifiers():
    ids = extract_identifiers("Reported in PMID: 31535829 and doi:10.1056/NEJMoa1911303, NCT03036124")
    assert ids["pmid"] == "31535829"
    assert ids["doi"] == "10.1056/nejmoa1911303"
    assert ids["nct"] == "NCT03036124"


def test_claim_resolved_by_pmid():
    claims = [{"claim_id": "c1", "text": "HR 0.74", "source": {"pmid": "31535829"}}]
    report = ground_claims(claims, _recs())
    assert report["grounded_count"] == 1
    assert report["grounding_ratio"] == 1.0
    assert report["claims"][0]["matched_record_id"] == "pmid:31535829"


def test_claim_resolved_by_doi_case_insensitive():
    claims = [{"claim_id": "c1", "text": "RR 0.70", "source": "DOI:10.1056/NEJMOA2022190"}]
    report = ground_claims(claims, _recs())
    assert report["grounded_count"] == 1


def test_claim_with_no_identifier_is_ungrounded():
    claims = [{"claim_id": "c1", "text": "The drug reduced events by 30%."}]
    report = ground_claims(claims, _recs())
    assert report["grounded_count"] == 0
    assert report["ungrounded_count"] == 1
    assert "no citation identifier" in report["ungrounded"][0]["reason"]


def test_identifier_present_but_unresolved():
    # well-formed but not in the corpus -> reported unresolved, NOT counted grounded
    claims = [{"claim_id": "c1", "text": "x", "source": {"pmid": "99999999"}}]
    report = ground_claims(claims, _recs())
    assert report["grounded_count"] == 0
    assert "does not resolve" in report["ungrounded"][0]["reason"]


def test_identifier_pulled_from_text_when_no_source():
    claims = [{"claim_id": "c1", "text": "As shown (doi:10.1056/NEJMoa1911303), HR 0.74."}]
    report = ground_claims(claims, _recs())
    assert report["grounded_count"] == 1


def test_empty_claims_ratio_is_none_not_one():
    report = ground_claims([], _recs())
    assert report["grounding_ratio"] is None
    assert report["claim_count"] == 0


def test_mixed_grounding_ratio_and_artifact(tmp_path):
    claims = [
        {"claim_id": "a", "text": "x", "source": {"pmid": "31535829"}},
        {"claim_id": "b", "text": "ungrounded claim"},
    ]
    report = ground_claims(claims, _recs(), artifacts_dir=tmp_path / "artifacts")
    assert report["grounding_ratio"] == 0.5
    written = json.loads((tmp_path / "artifacts" / "evidence" / "citation_grounding.json").read_text(encoding="utf-8"))
    assert written["capability"] == "citation_grounding"
    assert written["ungrounded_count"] == 1


def test_grounding_against_bundled_corpus():
    # the real seed corpus contains DAPA-HF (pmid 31535829)
    claims = [{"claim_id": "c1", "text": "HR 0.74", "source": {"pmid": "31535829"}}]
    report = ground_claims(claims, default_provider().records())
    assert report["grounded_count"] == 1
