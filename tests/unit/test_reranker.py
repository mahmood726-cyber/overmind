"""Unit tests for the cross-encoder reranker and store.rerank_search.

Robust to backend availability: the assertions that require the cross-encoder
model are guarded by ``reranker.is_available()``; the structural guarantees
(empty input, top_k truncation, graceful degradation) hold either way.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from overmind.memory import reranker
from overmind.memory.store import MemoryStore
from overmind.storage.db import StateDatabase
from overmind.storage.models import MemoryRecord


def _store(tmp_path: Path) -> tuple[MemoryStore, StateDatabase]:
    db = StateDatabase(tmp_path / "m.db")
    store = MemoryStore(db=db, checkpoints_dir=tmp_path / "cp", logs_dir=tmp_path / "logs")
    return store, db


def test_rerank_empty_returns_empty():
    assert reranker.rerank("q", [], text_of=lambda x: x) == []
    assert reranker.rerank_scores("q", []) == []


def test_rerank_top_k_truncates():
    cands = ["a", "b", "c", "d"]
    out = reranker.rerank("q", cands, text_of=lambda x: x, top_k=2)
    assert len(out) == 2
    # Every returned item is one of the inputs (no fabrication).
    assert set(out).issubset(set(cands))


def test_rerank_preserves_all_when_no_top_k():
    cands = ["a", "b", "c"]
    out = reranker.rerank("q", cands, text_of=lambda x: x)
    assert sorted(out) == sorted(cands)


@pytest.mark.skipif(not reranker.is_available(), reason="cross-encoder backend not installed")
def test_rerank_orders_relevant_first():
    query = "When did Caroline join the LGBTQ support group?"
    docs = [
        "The weather in Toronto was cold and rainy all week.",
        "Caroline: I finally joined an LGBTQ support group last month.",
        "We talked about our favourite pizza toppings.",
    ]
    scores = reranker.rerank_scores(query, docs)
    assert scores is not None
    # The relevant doc (index 1) must score highest.
    assert scores[1] == max(scores)
    ranked = reranker.rerank(query, docs, text_of=lambda x: x)
    assert ranked[0] == docs[1]


@pytest.mark.skipif(not reranker.is_available(), reason="cross-encoder backend not installed")
def test_store_rerank_search_returns_records_and_respects_limit(tmp_path):
    store, db = _store(tmp_path)
    try:
        from overmind.memory import embeddings

        texts = {
            "u1": "Caroline joined an LGBTQ support group in March.",
            "u2": "The recipe needs two cups of flour and one egg.",
            "u3": "Mark went hiking on the mountain trail on Sunday.",
            "u4": "Caroline said the support group meets every Tuesday evening.",
        }
        for uid, txt in texts.items():
            store.save(MemoryRecord(
                memory_id=uid, memory_type="project_learning", scope="bench",
                title=uid, content=txt, embedding=embeddings.embed(txt),
            ))
        out = store.rerank_search("When does Caroline's support group meet?", limit=2, candidate_pool=10)
        assert len(out) == 2
        assert all(isinstance(m, MemoryRecord) for m in out)
        # A support-group turn should surface in the top-2.
        assert any(m.memory_id in ("u1", "u4") for m in out)
    finally:
        db.close()


def test_store_rerank_search_degrades_without_embeddings(tmp_path, monkeypatch):
    """With no embeddings on records, the dense pool is empty -> rerank returns []."""
    store, db = _store(tmp_path)
    try:
        store.save(MemoryRecord(
            memory_id="n1", memory_type="project_learning", scope="bench",
            title="n1", content="no embedding here", embedding=None,
        ))
        out = store.rerank_search("anything", limit=5, candidate_pool=10)
        assert out == []
    finally:
        db.close()
