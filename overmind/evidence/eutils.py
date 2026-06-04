"""Optional LIVE scholarly corpus backend — NCBI E-utilities (PubMed).

This is the opt-in path that lifts the research-benchmark ``search_corpus`` score
from 2/3 (offline lexical seed) to 3/3 (retrieval from a large live scholarly
index). It is NEVER the default: nothing here runs unless a caller explicitly asks
for the live provider (``corpus-search --live`` / ``research-benchmark --live-corpus``).
The offline ``OfflineCorpusProvider`` remains the default for tests, nightly, and
offline e156 dashboards.

It uses the public NCBI E-utilities REST API (no auth required; an optional API key
raises the rate limit). Two calls per query: ``esearch`` (query -> PMIDs) then
``efetch`` (PMIDs -> article XML). Records are returned in the same dict shape as the
seed JSONL, so the rest of the evidence stack is provider-agnostic.

Network discipline (per the operating rules): bounded retries with backoff; explicit
handling of non-200, 429/5xx, and HTML error payloads (an error page is never treated
as data); fail closed on malformed/partial responses by raising ``EutilsError``.
"""
from __future__ import annotations

import json
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from xml.etree import ElementTree as ET

_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_TOOL = "overmind-evidence"
_EMAIL = "noreply@overmind.local"
_USER_AGENT = f"{_TOOL} (mailto:{_EMAIL})"
_MAX_RETRIES = 3
_BACKOFF_BASE = 0.8  # seconds; bounded exponential backoff
_BACKOFF_CAP = 8.0  # seconds; never sleep longer than this between attempts
_RETRY_AFTER_CAP = 30.0  # honor a server Retry-After, but never hang on a huge value
_MAX_BYTES = 25 * 1024 * 1024  # 25 MiB hard ceiling on any single response body
_EFETCH_POST_THRESHOLD = 200  # NCBI guidance: POST efetch when the id list is large
_PMID_RE = re.compile(r"^[0-9]+$")  # PubMed IDs are bare integers


class EutilsError(RuntimeError):
    """A live-fetch failure. Callers fail closed: no live artifact => no credit."""


def _parse_retry_after(headers) -> float | None:
    """Extract a Retry-After delay (delta-seconds form only) from an HTTPError's
    headers. The HTTP-date form is ignored (treated as absent) to keep this small;
    the fixed backoff still applies in that case."""
    getter = getattr(headers, "get", None)
    raw = getter("Retry-After") if callable(getter) else None
    if not raw:
        return None
    try:
        secs = float(str(raw).strip())
    except ValueError:
        return None
    return secs if secs >= 0 else None


def _backoff_delay(attempt: int, retry_after: float | None) -> float:
    """Exponential backoff, capped, honoring a (bounded) server Retry-After, plus a
    small jitter so concurrent callers don't synchronize their retries."""
    backoff = min(_BACKOFF_BASE * (2 ** attempt), _BACKOFF_CAP)
    if retry_after is not None:
        backoff = min(max(backoff, retry_after), _RETRY_AFTER_CAP)
    return backoff + random.uniform(0, _BACKOFF_BASE * 0.25)


def _http_get(url: str, *, timeout: float, expect: str, data: bytes | None = None) -> bytes:
    """HTTP GET (or POST when ``data`` is given) with bounded retry/backoff.
    ``expect`` is 'json' or 'xml'; an HTML/other error payload (Cloudflare/NCBI
    throttle page) is rejected, never parsed. Defenses applied before the body is
    trusted: host-pinning (a redirect off the requested host fails closed), a hard
    response size ceiling, BOM strip, and content-shape sniffing for the expected
    type."""
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    raise EutilsError(f"HTTP {resp.status} from {url}")
                # Host-pin: urlopen auto-follows 3xx; reject a body served from a
                # host other than the one we requested before reading it.
                req_host = urllib.parse.urlsplit(url).hostname
                final_host = urllib.parse.urlsplit(getattr(resp, "url", None) or url).hostname
                if req_host and final_host and final_host != req_host:
                    raise EutilsError(
                        f"redirected off {req_host!r} to unexpected host {final_host!r}")
                ctype = (resp.headers.get("Content-Type") or "").lower()
                body = resp.read(_MAX_BYTES + 1)
            if len(body) > _MAX_BYTES:
                raise EutilsError(f"oversized payload from {url} (> {_MAX_BYTES} bytes)")
            # Strip a leading BOM before sniffing the content shape.
            head = body[:512].lstrip(b"\xef\xbb\xbf").lstrip().lower()
            # An HTML body when we asked for json/xml is an error/throttle page.
            if head.startswith(b"<!doctype html") or head.startswith(b"<html"):
                raise EutilsError(f"HTML error payload from {url} (likely throttled)")
            if expect == "json":
                if "json" not in ctype and not head.startswith(b"{"):
                    raise EutilsError(f"expected JSON, got {ctype!r} from {url}")
            elif expect == "xml":
                # Reject plain-text/JSON error bodies (e.g. "Server busy") that
                # would otherwise reach the XML parser as garbage.
                if not head.startswith(b"<"):
                    raise EutilsError(f"expected XML, got {ctype!r} from {url}")
            return body
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, EutilsError) as exc:
            last_exc = exc
            # 4xx that is not 429 is not worth retrying
            status = getattr(exc, "code", None)
            if status is not None and 400 <= status < 500 and status != 429:
                raise EutilsError(f"non-retryable HTTP {status} from {url}") from exc
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_backoff_delay(attempt, _parse_retry_after(getattr(exc, "headers", None))))
    raise EutilsError(f"giving up on {url} after {_MAX_RETRIES} attempts: {last_exc}")


def esearch(query: str, limit: int, *, timeout: float = 15.0, api_key: str | None = None) -> list[str]:
    """Resolve a query to a list of PMIDs (most-relevant first)."""
    if not (query or "").strip():
        raise ValueError("query must be non-empty")
    params = {
        "db": "pubmed", "term": query, "retmode": "json",
        "retmax": str(max(1, int(limit))), "sort": "relevance",
        "tool": _TOOL, "email": _EMAIL,
    }
    if api_key:
        params["api_key"] = api_key
    url = f"{_BASE}/esearch.fcgi?{urllib.parse.urlencode(params)}"
    try:
        data = json.loads(_http_get(url, timeout=timeout, expect="json"))
    except json.JSONDecodeError as exc:
        raise EutilsError(f"esearch returned non-JSON: {exc}") from exc
    idlist = (data.get("esearchresult") or {}).get("idlist")
    if not isinstance(idlist, list):
        raise EutilsError("esearch response missing esearchresult.idlist")
    # Validate shape: a PubMed ID is a bare integer. Drop anything malformed/hostile
    # (it could never resolve via efetch anyway) and cap to the requested limit so a
    # misbehaving response cannot inflate the efetch id list.
    pmids = [s for s in (str(pid).strip() for pid in idlist) if _PMID_RE.match(s)]
    return pmids[: max(1, int(limit))]


def _text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return "".join(node.itertext()).strip()


def parse_efetch_xml(xml_bytes: bytes, query: str = "") -> list[dict]:
    """Parse a PubmedArticleSet efetch XML payload into seed-shaped record dicts.

    Pure function (no network) so it is unit-testable against a committed fixture.

    XML safety: stdlib ElementTree does not resolve external entities (XXE is not
    exploitable; an external-entity ref raises ParseError -> EutilsError). Internal
    entity-expansion ("billion laughs") is bounded by CPython's bundled expat
    (>= 2.4) amplification limits; the ``_MAX_BYTES`` ceiling in ``_http_get`` bounds
    the input size before it reaches the parser.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise EutilsError(f"efetch returned unparseable XML: {exc}") from exc

    records: list[dict] = []
    for art in root.findall(".//PubmedArticle"):
        medline = art.find("MedlineCitation")
        if medline is None:
            continue
        pmid = _text(medline.find("PMID"))
        article = medline.find("Article")
        if article is None or not pmid:
            continue
        title = _text(article.find("ArticleTitle"))
        if not title:
            continue  # title is the minimum groundable unit
        abstract = " ".join(
            _text(a) for a in article.findall(".//Abstract/AbstractText")
        ).strip()
        # DOI from the article id list
        doi = None
        for aid in art.findall(".//ArticleIdList/ArticleId"):
            if (aid.get("IdType") or "").lower() == "doi":
                doi = _text(aid) or None
                break
        # year
        year = None
        ytext = _text(article.find(".//Journal/JournalIssue/PubDate/Year"))
        if ytext.isdigit():
            year = int(ytext)
        journal = _text(article.find(".//Journal/Title"))
        authors = []
        for au in article.findall(".//AuthorList/Author"):
            last = _text(au.find("LastName"))
            inits = _text(au.find("Initials"))
            if last:
                authors.append((last + " " + inits).strip())
        ptypes = [_text(p) for p in article.findall(".//PublicationTypeList/PublicationType") if _text(p)]
        # ClinicalTrials.gov accession (NCT) from the DataBankList, if present.
        nct = None
        for db in article.findall(".//DataBankList/DataBank"):
            if _text(db.find("DataBankName")).lower() == "clinicaltrials.gov":
                for acc in db.findall(".//AccessionNumber"):
                    if _text(acc).upper().startswith("NCT"):
                        nct = _text(acc).upper()
                        break
            if nct:
                break
        records.append({
            "record_id": f"pmid:{pmid}",
            "source": "pubmed",
            "pmid": pmid,
            "doi": doi,
            "nct": nct,
            "title": title,
            "abstract": abstract,
            "year": year,
            "journal": journal,
            "authors": authors[:8],
            "article_types": ptypes,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "fetched_via": "ncbi-eutils",
            "fetched_query": query,
        })
    return records


def efetch(pmids: list[str], *, query: str = "", timeout: float = 20.0, api_key: str | None = None) -> list[dict]:
    if not pmids:
        return []
    params = {
        "db": "pubmed", "id": ",".join(pmids), "retmode": "xml",
        "tool": _TOOL, "email": _EMAIL,
    }
    if api_key:
        params["api_key"] = api_key
    encoded = urllib.parse.urlencode(params)
    base_url = f"{_BASE}/efetch.fcgi"
    # Per NCBI guidance, POST the id list once it is large, so a big PMID batch does
    # not blow past URL-length limits as an over-long GET query string.
    if len(pmids) > _EFETCH_POST_THRESHOLD:
        body = _http_get(base_url, timeout=timeout, expect="xml", data=encoded.encode())
    else:
        body = _http_get(f"{base_url}?{encoded}", timeout=timeout, expect="xml")
    return parse_efetch_xml(body, query=query)


def eutils_fetch(query: str, limit: int = 20, *, timeout: float = 20.0, api_key: str | None = None) -> list[dict]:
    """Live fetcher of shape ``(query, limit) -> list[dict]`` for injection into
    :class:`overmind.evidence.corpus.McpCorpusProvider`. Raises EutilsError on any
    network/parse failure so the caller fails closed (no live artifact => no credit)."""
    pmids = esearch(query, limit, timeout=timeout, api_key=api_key)
    return efetch(pmids, query=query, timeout=timeout, api_key=api_key)
