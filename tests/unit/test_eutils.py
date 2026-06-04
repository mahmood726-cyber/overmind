from __future__ import annotations

import urllib.error
from pathlib import Path

import pytest

from overmind.evidence import eutils
from overmind.evidence.eutils import EutilsError, parse_efetch_xml

_FIXTURE = Path(__file__).parent.parent / "data" / "eutils_efetch_sample.xml"


def _xml() -> bytes:
    return _FIXTURE.read_bytes()


class _FakeResp:
    """Minimal stand-in for an urllib response context manager."""

    def __init__(self, status=200, body=b"", ctype="application/json", url=None):
        self.status = status
        self._body = body if isinstance(body, bytes) else body.encode()
        self.headers = {"Content-Type": ctype}
        self.url = url  # None => _http_get falls back to the requested url (same host)

    def read(self, amt=None):
        # Mirror HTTPResponse.read(amt): the size-cap path passes a byte ceiling.
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _seq_urlopen(seq):
    """Return a fake urlopen that yields seq items in order (Exception -> raise)."""
    state = {"n": 0}

    def fake(req, timeout=None):
        item = seq[min(state["n"], len(seq) - 1)]
        state["n"] += 1
        if isinstance(item, Exception):
            raise item
        return item

    fake.state = state
    return fake


def _http_error(code, headers=None):
    return urllib.error.HTTPError("http://x", code, "err", headers or {}, None)


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


def test_parse_handles_real_world_variability():
    # Shapes common in real NEJM/Lancet efetch payloads that the bundled 2-record
    # fixture does not exercise (2026-06-04 review): an ArticleId list where pii/pmc
    # precede the doi, a title with inline markup, a CollectiveName-only author and an
    # author with no Initials, and a record with no Abstract element at all.
    xml = (
        b"<PubmedArticleSet><PubmedArticle>"
        b"<MedlineCitation><PMID>12345678</PMID><Article>"
        b"<ArticleTitle>Effect of <i>SGLT2</i> on H<sub>2</sub>O balance</ArticleTitle>"
        b"<Journal><Title>Lancet</Title></Journal>"
        b"<AuthorList>"
        b"<Author><CollectiveName>DAPA Study Group</CollectiveName></Author>"
        b"<Author><LastName>Smith</LastName></Author>"
        b"</AuthorList>"
        b"</Article></MedlineCitation>"
        b"<PubmedData><ArticleIdList>"
        b'<ArticleId IdType="pii">S0140-6736</ArticleId>'
        b'<ArticleId IdType="pmc">PMC7654321</ArticleId>'
        b'<ArticleId IdType="doi">10.1016/realworld</ArticleId>'
        b"</ArticleIdList></PubmedData>"
        b"</PubmedArticle></PubmedArticleSet>"
    )
    r = parse_efetch_xml(xml)[0]
    assert r["title"] == "Effect of SGLT2 on H2O balance"   # inline markup flattened
    assert r["doi"] == "10.1016/realworld"                  # doi found despite pii/pmc first
    assert r["abstract"] == ""                              # no Abstract element, not invented
    assert r["authors"] == ["Smith"]                        # no-initials kept; CollectiveName skipped


def test_parse_extracts_nct_from_databank():
    r = parse_efetch_xml(_xml())[0]
    assert r["nct"] == "NCT03036124"
    # second fixture record has no DataBank -> nct is None, not invented
    assert parse_efetch_xml(_xml())[1]["nct"] is None


# --- live-network fail-closed discipline (HIGH gap from 2026-06-04 review) ------

def test_http_get_rejects_html_throttle_payload(monkeypatch):
    monkeypatch.setattr(eutils.urllib.request, "urlopen",
                        _seq_urlopen([_FakeResp(200, b"<!DOCTYPE html><html>throttled</html>", "text/html")]))
    with pytest.raises(EutilsError, match="HTML error payload"):
        eutils._http_get("http://x", timeout=5, expect="json")


def test_http_get_rejects_non_json_when_json_expected(monkeypatch):
    monkeypatch.setattr(eutils.urllib.request, "urlopen",
                        _seq_urlopen([_FakeResp(200, b"plain not json", "text/plain")]))
    with pytest.raises(EutilsError, match="expected JSON"):
        eutils._http_get("http://x", timeout=5, expect="json")


def test_http_get_retries_429_then_succeeds(monkeypatch):
    sleeps = []
    monkeypatch.setattr(eutils.time, "sleep", lambda s: sleeps.append(s))
    fake = _seq_urlopen([_http_error(429), _FakeResp(200, b'{"ok":1}')])
    monkeypatch.setattr(eutils.urllib.request, "urlopen", fake)
    body = eutils._http_get("http://x", timeout=5, expect="json")
    assert body == b'{"ok":1}'
    assert fake.state["n"] == 2 and len(sleeps) == 1  # retried once, backed off once


def test_http_get_does_not_retry_404(monkeypatch):
    monkeypatch.setattr(eutils.time, "sleep", lambda s: (_ for _ in ()).throw(AssertionError("slept")))
    fake = _seq_urlopen([_http_error(404)])
    monkeypatch.setattr(eutils.urllib.request, "urlopen", fake)
    with pytest.raises(EutilsError, match="non-retryable HTTP 404"):
        eutils._http_get("http://x", timeout=5, expect="json")
    assert fake.state["n"] == 1  # called exactly once, no retry


def test_esearch_fails_closed_on_missing_idlist(monkeypatch):
    monkeypatch.setattr(eutils, "_http_get", lambda *a, **k: b'{"esearchresult":{}}')
    with pytest.raises(EutilsError, match="idlist"):
        eutils.esearch("query", 5)


def test_esearch_fails_closed_on_non_json(monkeypatch):
    monkeypatch.setattr(eutils, "_http_get", lambda *a, **k: b"<not json>")
    with pytest.raises(EutilsError):
        eutils.esearch("query", 5)


def test_esearch_empty_query_rejected():
    with pytest.raises(ValueError):
        eutils.esearch("   ", 5)


def test_eutils_fetch_empty_idlist_returns_empty(monkeypatch):
    monkeypatch.setattr(eutils, "esearch", lambda *a, **k: [])
    # efetch([]) must short-circuit to [] without a network call
    assert eutils.eutils_fetch("query", 5) == []


# --- network hardening (LOW cluster from 2026-06-04 review) ---------------------

def test_http_get_rejects_oversized_payload(monkeypatch):
    monkeypatch.setattr(eutils, "_MAX_BYTES", 10)
    # body exceeds the (patched) ceiling; shape is valid XML so only size trips it.
    monkeypatch.setattr(eutils.urllib.request, "urlopen",
                        _seq_urlopen([_FakeResp(200, b"<" + b"x" * 50, "application/xml")]))
    with pytest.raises(EutilsError, match="oversized payload"):
        eutils._http_get("http://x", timeout=5, expect="xml")


def test_http_get_honors_retry_after_header(monkeypatch):
    sleeps = []
    monkeypatch.setattr(eutils.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(eutils.random, "uniform", lambda a, b: 0.0)  # kill jitter
    fake = _seq_urlopen([_http_error(429, {"Retry-After": "2"}), _FakeResp(200, b'{"ok":1}')])
    monkeypatch.setattr(eutils.urllib.request, "urlopen", fake)
    assert eutils._http_get("http://x", timeout=5, expect="json") == b'{"ok":1}'
    # the fixed first backoff is 0.8s; Retry-After of 2s must win
    assert sleeps == [2.0]


def test_http_get_rejects_redirect_to_other_host(monkeypatch):
    monkeypatch.setattr(eutils.time, "sleep", lambda s: None)
    resp = _FakeResp(200, b'{"ok":1}', url="https://evil.example.com/x")
    monkeypatch.setattr(eutils.urllib.request, "urlopen", _seq_urlopen([resp]))
    with pytest.raises(EutilsError, match="unexpected host"):
        eutils._http_get("https://eutils.ncbi.nlm.nih.gov/e.fcgi", timeout=5, expect="json")


def test_http_get_rejects_non_xml_when_xml_expected(monkeypatch):
    # a plain-text throttle body ("Server busy") must not reach the XML parser
    monkeypatch.setattr(eutils.urllib.request, "urlopen",
                        _seq_urlopen([_FakeResp(200, b"Server busy, try later", "text/plain")]))
    with pytest.raises(EutilsError, match="expected XML"):
        eutils._http_get("http://x", timeout=5, expect="xml")


def test_esearch_drops_non_numeric_pmids_and_caps(monkeypatch):
    monkeypatch.setattr(
        eutils, "_http_get",
        lambda *a, **k: b'{"esearchresult":{"idlist":["123"," 45 ","abc","","678"]}}')
    # 'abc'/'' dropped; whitespace trimmed; capped to limit=2
    assert eutils.esearch("query", 2) == ["123", "45"]


def test_efetch_uses_post_for_large_idlist(monkeypatch):
    captured = {}

    def fake_http_get(url, *, timeout, expect, data=None):
        captured["url"] = url
        captured["data"] = data
        return _xml()

    monkeypatch.setattr(eutils, "_http_get", fake_http_get)
    big = [str(n) for n in range(eutils._EFETCH_POST_THRESHOLD + 1)]
    recs = eutils.efetch(big)
    assert len(recs) == 2  # parsed from the fixture
    assert captured["data"] is not None  # POST body, not a GET query string
    assert "?" not in captured["url"]  # ids not in the URL


def test_efetch_uses_get_for_small_idlist(monkeypatch):
    captured = {}

    def fake_http_get(url, *, timeout, expect, data=None):
        captured["url"] = url
        captured["data"] = data
        return _xml()

    monkeypatch.setattr(eutils, "_http_get", fake_http_get)
    eutils.efetch(["123", "456"])
    assert captured["data"] is None  # GET
    assert "id=123%2C456" in captured["url"]
