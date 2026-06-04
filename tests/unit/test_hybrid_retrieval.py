from __future__ import annotations

import math

from overmind.evidence.corpus import CorpusRecord, rank
from overmind.evidence.hybrid_retrieval import (
    HybridRanker,
    char_ngram_vector,
    cosine,
    reciprocal_rank_fusion,
)


def _recs(specs):
    return [CorpusRecord(record_id=i, title=t, abstract=a) for i, t, a in specs]


def test_char_ngram_cosine_basics():
    v = char_ngram_vector("cardioprotection")
    assert math.isclose(cosine(v, v), 1.0, abs_tol=1e-9)            # self-similarity = 1
    assert cosine(char_ngram_vector("apple"), char_ngram_vector("zzzzz")) == 0.0  # disjoint
    # morphological variants are highly similar (the whole point)
    assert cosine(char_ngram_vector("anticoagulation"), char_ngram_vector("anticoagulant")) > 0.4


def test_rrf_fuses_rankings():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "a", "d"]], k=60)
    # 'a' and 'b' appear high in both -> outrank singletons c,d
    assert fused["a"] > fused["c"] and fused["b"] > fused["d"]


def test_hybrid_recovers_vocabulary_mismatch_bm25_misses():
    recs = _recs([
        ("variant", "Cardioprotective therapy in cardiology", "the drug showed cardioprotective effects"),
        ("exact", "Cardioprotection mechanisms", "a direct cardioprotection pathway"),
        ("off", "Geology of sandstone basins", "sedimentary desert deposition"),
    ])
    # BM25 alone: query token 'cardioprotection' does NOT token-match 'cardioprotective'
    bm25_ids = {h.record.record_id for h in rank(recs, "cardioprotection", limit=10)}
    assert "variant" not in bm25_ids        # BM25 misses the morphological variant

    out = HybridRanker().rank(recs, "cardioprotection", limit=10)
    hit_ids = {h["record_id"] for h in out["hits"]}
    assert "variant" in hit_ids and "exact" in hit_ids   # hybrid surfaces both
    assert "off" not in hit_ids
    variant_hit = next(h for h in out["hits"] if h["record_id"] == "variant")
    assert variant_hit["vector_recovered"] is True       # recovered by the vector signal


def test_offline_default_does_not_claim_neural():
    out = HybridRanker().rank(_recs([("a", "heart failure", "trial"), ("b", "x", "y")]), "heart failure")
    assert out["uses_dense"] is False
    assert "dense-embeddings" not in out["method"]
    assert out["method"] == "rrf(bm25 + char-ngram-cosine)"
    assert "no neural embeddings" in out["note"]


def test_determinism():
    recs = _recs([("a", "heart failure dapagliflozin", "sglt2"), ("b", "heart failure empagliflozin", "sglt2"),
                  ("c", "unrelated", "topic")])
    a = HybridRanker().rank(recs, "heart failure", limit=5)
    b = HybridRanker().rank(recs, "heart failure", limit=5)
    assert a == b


def test_optin_dense_is_labelled_and_fused():
    # a deterministic fake embed backend (NOT neural — stands in for an opt-in provider)
    def fake_embed(texts):
        # 2-d vector: [len, count of 'heart'] — deterministic, just to exercise fusion
        return [[float(len(t)), float(t.lower().count("heart"))] for t in texts]

    ranker = HybridRanker(embed=fake_embed)
    assert ranker.uses_dense is True
    out = ranker.rank(_recs([("a", "heart failure", "trial"), ("b", "x", "y")]), "heart failure")
    assert out["uses_dense"] is True
    assert "dense-embeddings" in out["method"]
    assert "opt-in backend bound" in out["note"]
