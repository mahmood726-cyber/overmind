"""Scholarly corpus access + offline ranked retrieval.

Closes the research-benchmark ``search_corpus`` gap (was hardcoded 0/3: "no
corpus-search subsystem"). The model mirrors Sentinel's ``citation_resolution``
rule: slow/network-bound fetching happens OUT OF BAND and is committed as a
fixture; the runtime path is offline, deterministic, and makes no network call.

Providers
---------
``OfflineCorpusProvider``  — DEFAULT. Reads a committed JSONL corpus (one record
    per line). The bundled seed (``data/corpus_seed.jsonl``) was fetched via the
    PubMed MCP tool and contains only real, DOI-resolvable records.
``McpCorpusProvider``      — OPTIONAL. Documents the live PubMed/Scholar MCP
    contract. It declares ``available=False`` unless a caller injects a live
    ``fetch`` callable, so the nightly/offline path never silently depends on a
    network backend and scoring never credits a search that did not run.

Ranking
-------
``rank()`` is a self-contained BM25 (Robertson/Spärck Jones; k1=1.5, b=0.75) over
title+abstract. Deterministic, stdlib-only. It is a real retrieval function, not a
substring filter — but it is a lexical baseline, not a semantic index, and the
artifact says so. Empty/whitespace queries fail closed (ValueError), per the
"validate >0 rows" rule.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Protocol, runtime_checkable

_DATA_DIR = Path(__file__).resolve().parent / "data"
_SEED_CORPUS = _DATA_DIR / "corpus_seed.jsonl"

# Small, deliberately conservative stopword set. Kept tiny so domain terms that
# look like stopwords elsewhere (e.g. "control") are never dropped.
_STOPWORDS = frozenset(
    "a an and are as at be but by for if in into is it no not of on or such that "
    "the their then there these they this to was will with we our".split()
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")

_BM25_K1 = 1.5
_BM25_B = 0.75


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens with stopwords removed. Deterministic."""
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOPWORDS]


@dataclass(frozen=True, slots=True)
class CorpusRecord:
    """One scholarly record. ``record_id`` is the stable join key used by the
    screening, extraction, and citation-grounding modules downstream."""

    record_id: str
    title: str
    abstract: str = ""
    source: str = "unknown"
    pmid: str | None = None
    doi: str | None = None
    year: int | None = None
    journal: str = ""
    authors: list[str] = field(default_factory=list)
    article_types: list[str] = field(default_factory=list)
    url: str = ""
    fetched_via: str = ""
    fetched_query: str = ""

    @classmethod
    def from_dict(cls, raw: dict) -> "CorpusRecord":
        rid = (raw.get("record_id") or "").strip()
        if not rid:
            pmid = raw.get("pmid")
            doi = raw.get("doi")
            rid = f"pmid:{pmid}" if pmid else (f"doi:{doi}" if doi else "")
        if not rid:
            raise ValueError("corpus record is missing record_id / pmid / doi")
        if not (raw.get("title") or "").strip():
            # Title is the minimum groundable unit; a record with no title cannot
            # be screened or cited. Fail closed rather than admit a blank record.
            raise ValueError(f"corpus record {rid!r} has no title")
        year = raw.get("year")
        return cls(
            record_id=rid,
            title=raw["title"].strip(),
            abstract=(raw.get("abstract") or "").strip(),
            source=raw.get("source") or "unknown",
            pmid=raw.get("pmid"),
            doi=raw.get("doi"),
            year=int(year) if year else None,
            journal=raw.get("journal") or "",
            authors=list(raw.get("authors") or []),
            article_types=list(raw.get("article_types") or []),
            url=raw.get("url") or "",
            fetched_via=raw.get("fetched_via") or "",
            fetched_query=raw.get("fetched_query") or "",
        )

    @property
    def searchable_text(self) -> str:
        return f"{self.title}\n{self.abstract}"


@dataclass(frozen=True, slots=True)
class CorpusHit:
    record: CorpusRecord
    score: float
    matched_terms: list[str]

    def to_dict(self) -> dict:
        return {
            "record_id": self.record.record_id,
            "score": round(self.score, 4),
            "matched_terms": list(self.matched_terms),
            "title": self.record.title,
            "doi": self.record.doi,
            "pmid": self.record.pmid,
            "year": self.record.year,
            "source": self.record.source,
            "url": self.record.url,
        }


@runtime_checkable
class CorpusProvider(Protocol):
    """A source of :class:`CorpusRecord`. Implementations MUST be honest about
    ``available``: it is False whenever the provider cannot actually return
    records (missing fixture, unbound live backend), so downstream scoring never
    credits a search that could not run."""

    name: str

    @property
    def available(self) -> bool: ...

    def records(self) -> list[CorpusRecord]: ...


class OfflineCorpusProvider:
    """Reads a committed JSONL corpus. Default and nightly-safe."""

    name = "offline-jsonl"

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else _SEED_CORPUS
        self._cache: list[CorpusRecord] | None = None

    @property
    def available(self) -> bool:
        try:
            return self.path.is_file() and self.path.stat().st_size > 0
        except OSError:
            return False

    def records(self) -> list[CorpusRecord]:
        if self._cache is not None:
            return self._cache
        out: list[CorpusRecord] = []
        if not self.path.is_file():
            self._cache = out
            return out
        seen: set[str] = set()
        with self.path.open(encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                    rec = CorpusRecord.from_dict(raw)
                except (json.JSONDecodeError, ValueError) as exc:
                    raise ValueError(f"{self.path}:{lineno}: bad corpus record: {exc}") from exc
                if rec.record_id in seen:
                    continue  # de-dup on the stable join key
                seen.add(rec.record_id)
                out.append(rec)
        self._cache = out
        return out


class McpCorpusProvider:
    """Optional live provider over PubMed/Scholar MCP.

    Intentionally inert unless a caller injects a ``fetch`` callable of shape
    ``fetch(query: str, limit: int) -> list[dict]`` returning raw records in the
    same shape as the seed JSONL. With no fetcher it reports ``available=False`` —
    so the default/nightly path can construct it without acquiring a network
    dependency, and the benchmark will not credit corpus search through it.

    The live binding is deliberately NOT wired to the ambient MCP client here:
    per the lessons file, an unpinned MCP descriptor is a P0-equivalent risk, and
    headless/cron runs may not have the interactively-authenticated MCP server.
    """

    def __init__(self, fetch: Callable[[str, int], Iterable[dict]] | None = None,
                 name: str = "mcp-live") -> None:
        self._fetch = fetch
        self._last: list[CorpusRecord] = []
        self.name = name

    @property
    def available(self) -> bool:
        return self._fetch is not None

    def query(self, query: str, limit: int = 50) -> list[CorpusRecord]:
        if self._fetch is None:
            raise RuntimeError(
                "McpCorpusProvider has no fetcher bound; inject a fetch callable "
                "(query, limit) -> list[dict] to use the live PubMed/Scholar path."
            )
        if not (query or "").strip():
            raise ValueError("query must be non-empty")
        self._last = [CorpusRecord.from_dict(r) for r in self._fetch(query, limit)]
        return self._last

    def records(self) -> list[CorpusRecord]:
        return list(self._last)


def default_provider() -> OfflineCorpusProvider:
    """The provider used by the CLI and the benchmark unless overridden."""
    return OfflineCorpusProvider()


def live_pubmed_provider(api_key: str | None = None) -> "McpCorpusProvider":
    """OPT-IN live provider backed by NCBI E-utilities (PubMed). Network-dependent;
    never the default. Lifts search_corpus from a strong-partial (2) offline seed to
    first-class (3) retrieval over a large live index — but only when it actually
    returns hits, so scoring stays honest."""
    from overmind.evidence.eutils import eutils_fetch

    def _fetch(query: str, limit: int) -> list[dict]:
        return eutils_fetch(query, limit, api_key=api_key)

    return McpCorpusProvider(fetch=_fetch, name="pubmed-eutils")


def rank(records: list[CorpusRecord], query: str, limit: int = 10) -> list[CorpusHit]:
    """BM25 ranking of ``records`` against ``query``. Deterministic; ties broken
    by record_id for stable output. Raises on an empty query (fail closed)."""
    q_terms = tokenize(query)
    if not q_terms:
        raise ValueError("query produced no searchable terms (empty or all-stopword)")
    if not records:
        return []

    docs_tokens = [tokenize(r.searchable_text) for r in records]
    n = len(records)
    avgdl = sum(len(t) for t in docs_tokens) / n if n else 0.0

    # document frequency per term
    df: dict[str, int] = {}
    for tokens in docs_tokens:
        for term in set(tokens):
            df[term] = df.get(term, 0) + 1

    q_unique = list(dict.fromkeys(q_terms))  # preserve order, de-dup
    idf = {
        term: math.log(1 + (n - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5))
        for term in q_unique
    }

    hits: list[CorpusHit] = []
    for rec, tokens in zip(records, docs_tokens):
        dl = len(tokens)
        tf: dict[str, int] = {}
        for tok in tokens:
            tf[tok] = tf.get(tok, 0) + 1
        score = 0.0
        matched: list[str] = []
        for term in q_unique:
            f = tf.get(term, 0)
            if f == 0:
                continue
            matched.append(term)
            denom = f + _BM25_K1 * (1 - _BM25_B + _BM25_B * (dl / avgdl if avgdl else 0.0))
            score += idf[term] * (f * (_BM25_K1 + 1)) / denom if denom else 0.0
        if score > 0:
            hits.append(CorpusHit(record=rec, score=score, matched_terms=matched))

    hits.sort(key=lambda h: (-h.score, h.record.record_id))
    return hits[:limit]


class CorpusSearch:
    """Orchestrates a provider + ranking and writes an auditable artifact.

    The artifact (``<artifacts>/evidence/corpus_search.json``) is what the research
    benchmark reads to credit the ``search_corpus`` capability: it records the
    provider, corpus size, query, and ranked hits with provenance. No artifact, or
    an empty corpus, means no credit.
    """

    def __init__(self, provider: CorpusProvider | None = None, artifacts_dir: Path | None = None) -> None:
        self.provider = provider or default_provider()
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else None

    def _records_for(self, query: str, limit: int) -> list[CorpusRecord]:
        """Offline providers expose a fixed corpus via records(); live providers
        expose query() — fetch a candidate pool for THIS query, then BM25 re-rank it
        with the same ranking function so behaviour is uniform across providers."""
        live_query = getattr(self.provider, "query", None)
        if callable(live_query):
            return live_query(query, max(limit * 3, 25))
        return self.provider.records()

    def search(self, query: str, limit: int = 10) -> list[CorpusHit]:
        return rank(self._records_for(query, limit), query, limit=limit)

    def run(self, query: str, limit: int = 10) -> dict:
        records = self._records_for(query, limit)
        hits = rank(records, query, limit=limit)
        report = {
            "capability": "search_corpus",
            "provider": self.provider.name,
            "provider_available": bool(self.provider.available),
            "corpus_size": len(records),
            "sources": sorted({r.source for r in records}),
            "query": query,
            "limit": limit,
            "hit_count": len(hits),
            "hits": [h.to_dict() for h in hits],
            "ranking": "bm25(k1=1.5,b=0.75) lexical over title+abstract; not semantic",
        }
        if self.artifacts_dir is not None:
            out_dir = self.artifacts_dir / "evidence"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "corpus_search.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        return report
