from __future__ import annotations

from pathlib import Path

import pytest

from overmind.evidence.eutils import EutilsError, parse_efetch_xml

_FIXTURE = Path(__file__).parent.parent / "data" / "eutils_efetch_sample.xml"


def _xml() -> bytes:
    return _FIXTURE.read_bytes()


def test_parse_extracts_full_record():
    recs = parse_efetch_xml(_xml(), query="dapagliflozin")
    assert len(recs) == 2
    r = recs[0]
    assert r["record_id"] == "pmid:31535829"
    assert r["pmid"] == "31535829"
    assert r["doi"] == "10.1056/NEJMoa1911303"
    assert r["title"].startswith("Dapagliflozin in Patients")
    assert r["year"] == 2019
    assert r["journal"] == "The New England journal of medicine"
    assert r["source"] == "pubmed"
    assert r["fetched_via"] == "ncbi-eutils"
    assert r["fetched_query"] == "dapagliflozin"
    assert r["url"] == "https://pubmed.ncbi.nlm.nih.gov/31535829/"


def test_parse_joins_multipart_abstract():
    r = parse_efetch_xml(_xml())[0]
    # both AbstractText parts present in one string
    assert "SGLT2 inhibitors may reduce events" in r["abstract"]
    assert "hazard ratio, 0.74" in r["abstract"]


def test_parse_extracts_authors_and_types():
    r = parse_efetch_xml(_xml())[0]
    assert r["authors"] == ["McMurray JJV", "Solomon SD"]
    assert "Randomized Controlled Trial" in r["article_types"]


def test_parse_doi_null_path():
    # second fixture record has no DOI ArticleId -> doi must be None, not invented
    r = parse_efetch_xml(_xml())[1]
    assert r["pmid"] == "99999999"
    assert r["doi"] is None
    assert r["year"] == 2024


def test_parse_records_are_corpusrecord_compatible():
    from overmind.evidence.corpus import CorpusRecord
    for raw in parse_efetch_xml(_xml()):
        rec = CorpusRecord.from_dict(raw)  # must not raise
        assert rec.record_id and rec.title


def test_malformed_xml_fails_closed():
    with pytest.raises(EutilsError):
        parse_efetch_xml(b"<not><valid")


def test_empty_articleset_yields_no_records():
    assert parse_efetch_xml(b"<PubmedArticleSet></PubmedArticleSet>") == []
