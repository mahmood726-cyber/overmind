"""Tests for the optional RAG/embeddings layer (design point 2)."""
from __future__ import annotations

import json
from pathlib import Path

from overmind.retrieval.embeddings import HashingEmbedder, LocalEmbedder, build_embedder
from overmind.retrieval.vector_store import InMemoryVectorStore
from overmind.retrieval.retriever import Retriever, is_rag_enabled


# ── embeddings ──────────────────────────────────────────────────────


def test_hashing_embedder_deterministic():
    e = HashingEmbedder(dim=64)
    assert e.embed("hello world") == e.embed("hello world")
    assert len(e.embed("x")) == 64


def test_hashing_embedder_normalised():
    v = HashingEmbedder().embed("some words here for embedding")
    norm = sum(x * x for x in v) ** 0.5
    assert abs(norm - 1.0) < 1e-9


def test_hashing_embedder_empty_text_safe():
    v = HashingEmbedder(dim=32).embed("")
    assert v == [0.0] * 32


def test_build_embedder_default_is_hashing():
    assert isinstance(build_embedder(), HashingEmbedder)


def test_build_embedder_local_selectable():
    assert isinstance(build_embedder("local"), LocalEmbedder)


def test_local_embedder_uses_endpoint_then_falls_back():
    e = LocalEmbedder(http=lambda u, p, t: json.dumps({"embedding": [0.0, 3.0, 4.0]}))
    v = e.embed("hi")
    assert abs((sum(x * x for x in v) ** 0.5) - 1.0) < 1e-9  # normalised
    # On error, falls back to hashing (no raise)
    bad = LocalEmbedder(http=lambda u, p, t: (_ for _ in ()).throw(OSError("down")))
    assert len(bad.embed("hi")) == bad.dim


# ── vector store ────────────────────────────────────────────────────


def test_vector_store_search_orders_by_similarity():
    e = HashingEmbedder()
    store = InMemoryVectorStore()
    store.add("a", e.embed("python testing pytest"), "python testing pytest")
    store.add("b", e.embed("banana smoothie recipe"), "banana smoothie recipe")
    hits = store.search(e.embed("pytest python unit test"), k=2)
    assert hits[0].doc_id == "a"
    assert hits[0].score >= hits[1].score


def test_vector_store_empty_returns_nothing():
    assert InMemoryVectorStore().search([0.1, 0.2], k=3) == []


# ── retriever: OFF by default ───────────────────────────────────────


def test_rag_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OVERMIND_RAG_ENABLED", raising=False)
    assert is_rag_enabled() is False


def test_retriever_noop_when_disabled(tmp_path: Path):
    (tmp_path / "doc.md").write_text("grounding content about widgets", encoding="utf-8")
    r = Retriever(enabled=False)
    assert r.index_paths([tmp_path]) == 0
    assert r.retrieve("widgets") == []
    assert len(r.store) == 0


def test_retriever_indexes_and_retrieves_when_enabled(tmp_path: Path):
    (tmp_path / "a.md").write_text("Overmind verifies projects with witnesses.\n\nDeterministic gate.", encoding="utf-8")
    (tmp_path / "b.txt").write_text("Unrelated text about cooking pasta.", encoding="utf-8")
    r = Retriever(enabled=True, max_chars=200)
    n = r.index_paths([tmp_path])
    assert n >= 2
    hits = r.retrieve("how does Overmind verify projects", k=1)
    assert hits and "Overmind" in hits[0].text


def test_retriever_env_flag_controls_enable(monkeypatch):
    monkeypatch.setenv("OVERMIND_RAG_ENABLED", "1")
    assert Retriever().enabled is True
    monkeypatch.setenv("OVERMIND_RAG_ENABLED", "0")
    assert Retriever().enabled is False


def test_index_text_chunks_long_paragraph():
    r = Retriever(enabled=True, max_chars=50)
    n = r.index_text("doc", "x" * 130)
    assert n == 3  # 50 + 50 + 30
