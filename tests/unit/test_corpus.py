from __future__ import annotations

import json

import pytest

from overmind.evidence.corpus import (
    CorpusRecord,
    CorpusSearch,
    McpCorpusProvider,
    OfflineCorpusProvider,
    default_provider,
    rank,
    tokenize,
)


def _write_corpus(path, records):
    with path.open("w", encoding="utf-8") as handle:
        for rec in records:
            handle.write(json.dumps(rec) + "\n")
    return path


# --- bundled seed corpus -------------------------------------------------

def test_bundled_seed_loads_and_is_nonempty():
    provider = default_provider()
    assert provider.available is True
    records = provider.records()
    assert len(records) >= 5
    # every record is groundable: has an id, a title, and a real source
    for rec in records:
        assert rec.record_id
        assert rec.title
        assert rec.source == "pubmed"
        # seed was fetched out-of-band and carries provenance
        assert rec.fetched_via == "pubmed-mcp"


def test_seed_records_carry_resolvable_identifiers():
    # The seed must contain real, DOI-bearing records — no fabricated citations.
    records = default_provider().records()
    with_doi = [r for r in records if r.doi]
    assert len(with_doi) >= 5
    for rec in with_doi:
        assert rec.doi.startswith("10.")  # well-formed DOI prefix


# --- ranking -------------------------------------------------------------

def test_rank_orders_relevant_first():
    records = default_provider().records()
    hits = rank(records, "empagliflozin heart failure", limit=5)
    assert hits, "expected at least one hit for a corpus topic term"
    # scores are monotonically non-increasing
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)
    # the top hit actually contains a query term
    assert hits[0].matched_terms


def test_rank_is_deterministic():
    records = default_provider().records()
    a = [(h.record.record_id, round(h.score, 6)) for h in rank(records, "dapagliflozin", limit=10)]
    b = [(h.record.record_id, round(h.score, 6)) for h in rank(records, "dapagliflozin", limit=10)]
    assert a == b


def test_empty_query_fails_closed():
    records = default_provider().records()
    with pytest.raises(ValueError):
        rank(records, "   ")
    with pytest.raises(ValueError):
        rank(records, "the and of")  # all stopwords


def test_rank_on_empty_corpus_returns_empty():
    assert rank([], "anything") == []


def test_tokenize_drops_stopwords_keeps_domain_terms():
    toks = tokenize("The control arm of the trial")
    assert "the" not in toks and "of" not in toks
    assert "control" in toks and "trial" in toks


# --- offline provider mechanics -----------------------------------------

def test_offline_provider_dedups_on_record_id(tmp_path):
    path = _write_corpus(
        tmp_path / "c.jsonl",
        [
            {"record_id": "pmid:1", "title": "First", "source": "pubmed"},
            {"record_id": "pmid:1", "title": "Duplicate", "source": "pubmed"},
            {"record_id": "pmid:2", "title": "Second", "source": "pubmed"},
        ],
    )
    records = OfflineCorpusProvider(path).records()
    assert [r.record_id for r in records] == ["pmid:1", "pmid:2"]


def test_offline_provider_missing_file_is_unavailable(tmp_path):
    provider = OfflineCorpusProvider(tmp_path / "nope.jsonl")
    assert provider.available is False
    assert provider.records() == []


def test_record_without_title_fails_closed(tmp_path):
    path = _write_corpus(tmp_path / "c.jsonl", [{"record_id": "pmid:1", "title": "  "}])
    with pytest.raises(ValueError):
        OfflineCorpusProvider(path).records()


def test_record_id_synthesized_from_pmid():
    rec = CorpusRecord.from_dict({"pmid": "42", "title": "X"})
    assert rec.record_id == "pmid:42"


def test_non_integer_year_degrades_to_none_not_abort(tmp_path):
    # regression (2026-06-04 review): a non-numeric year must not abort the load
    rec = CorpusRecord.from_dict({"pmid": "1", "title": "X", "year": "2023 Mar"})
    assert rec.year is None
    # and a whole corpus with such a record still loads
    path = _write_corpus(tmp_path / "c.jsonl", [{"pmid": "1", "title": "X", "year": "n/a"}])
    assert len(OfflineCorpusProvider(path).records()) == 1


# --- live MCP provider is honest about availability ----------------------

def test_mcp_provider_unavailable_without_fetcher():
    provider = McpCorpusProvider()
    assert provider.available is False
    with pytest.raises(RuntimeError):
        provider.query("anything")


def test_mcp_provider_uses_injected_fetcher():
    def fake_fetch(query, limit):
        assert query and limit
        return [{"pmid": "9", "title": "Injected record", "source": "pubmed"}]

    provider = McpCorpusProvider(fetch=fake_fetch)
    assert provider.available is True
    records = provider.query("test", limit=3)
    assert records[0].record_id == "pmid:9"
    assert provider.records()[0].title == "Injected record"


# --- artifact contract (what the benchmark reads) ------------------------

def test_corpus_search_uses_queryable_live_provider(tmp_path):
    # A live-style provider exposes query(); CorpusSearch must fetch-then-rank it and
    # report it as a non-offline provider (the precondition for search_corpus=3).
    def fake_fetch(query, limit):
        assert query and limit >= 1
        return [
            {"pmid": "1", "title": "Dapagliflozin in heart failure", "source": "pubmed",
             "abstract": "randomized trial of dapagliflozin"},
            {"pmid": "2", "title": "Unrelated nutrition survey", "source": "pubmed"},
        ]

    provider = McpCorpusProvider(fetch=fake_fetch, name="pubmed-eutils")
    report = CorpusSearch(provider=provider, artifacts_dir=tmp_path / "artifacts").run(
        "dapagliflozin heart failure", limit=5)
    assert report["provider"] == "pubmed-eutils"
    assert report["provider_available"] is True
    assert report["hit_count"] >= 1
    # the relevant record ranks first
    assert report["hits"][0]["record_id"] == "pmid:1"


def test_live_pubmed_provider_factory_is_unbound_offline(monkeypatch):
    # The factory builds a provider whose name marks it non-offline; it stays inert
    # (and importable) without touching the network at construction time.
    from overmind.evidence.corpus import live_pubmed_provider
    provider = live_pubmed_provider()
    assert provider.name == "pubmed-eutils"
    assert provider.available is True  # a fetcher is bound, but no call made yet


def test_corpus_search_writes_artifact(tmp_path):
    artifacts = tmp_path / "artifacts"
    report = CorpusSearch(artifacts_dir=artifacts).run("empagliflozin", limit=3)
    assert report["capability"] == "search_corpus"
    assert report["provider"] == "offline-jsonl"
    assert report["provider_available"] is True
    assert report["corpus_size"] >= 5
    assert report["sources"] == ["pubmed"]
    written = json.loads((artifacts / "evidence" / "corpus_search.json").read_text(encoding="utf-8"))
    assert written["query"] == "empagliflozin"
    assert written["hit_count"] == len(written["hits"])
    if written["hits"]:
        assert "doi" in written["hits"][0] and "record_id" in written["hits"][0]
