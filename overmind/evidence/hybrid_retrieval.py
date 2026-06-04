"""Hybrid retrieval — BM25 fused with a vector signal, without diluting the truth lead.

The corpus search is lexical BM25, which misses vocabulary mismatch: a query for
"anticoagulation" does not token-match a paper titled "anticoagulant therapy", and
the discovery-recall literature (OpenScholar, PaperQA2) shows this gap matters.

This adds a SECOND signal and fuses the two by Reciprocal Rank Fusion (RRF). Two
honesty rules, by construction:

  1. The OFFLINE DEFAULT signal is a deterministic CHARACTER-N-GRAM cosine over
     title+abstract. It catches morphological / lexical-variant similarity BM25
     misses. It is NOT neural and is NOT called "dense embeddings" anywhere — it is
     labelled exactly as char-ngram vector similarity. Same input -> same bits.
  2. REAL dense embeddings are STRICTLY OPT-IN: bind an ``embed`` callable (a
     network/model backend, like the live-PubMed provider) and it is fused as a
     third ranking, with the method label upgraded to record that neural embeddings
     were actually used. With no embed bound, nothing claims neural semantics.

Stdlib-only in the default path; deterministic; offline.

NOTE on scope: this ranker is NOT wired into the benchmark's scored ``search_corpus``
path — ``CorpusSearch.run`` (the artifact the research-benchmark scores) uses plain
BM25 and labels itself "lexical ... not semantic". HybridRanker is an available,
unit-tested capability; the system does NOT credit its recall gain in any score. Wire
it into ``CorpusSearch`` if you want the gain measured in the benchmark.
"""
from __future__ import annotations

import math
import re
from typing import Callable

from overmind.evidence.corpus import CorpusHit, CorpusRecord, rank

_NGRAM_N = 3
_NONALNUM = re.compile(r"[^a-z0-9]+")
_RRF_K = 60  # standard RRF damping constant
# Below this char-ngram cosine, two strings merely share common English trigrams
# (ion/tio/ing/...) rather than a stem/lexical variant. Real morphological variants
# (anticoagulation~anticoagulant, cardioprotection~cardioprotective) score 0.4+;
# unrelated medical prose scores ~0.05-0.12. 0.15 separates signal from that noise.
_NGRAM_NOISE_FLOOR = 0.15


def _norm_text(text: str) -> str:
    return _NONALNUM.sub(" ", (text or "").lower()).strip()


def char_ngram_vector(text: str, n: int = _NGRAM_N) -> dict[str, float]:
    """L2-normalised term-frequency vector of character n-grams (with a leading/
    trailing space sentinel so word boundaries count). Deterministic."""
    s = f" {_norm_text(text)} "
    if len(s) < n:
        return {}
    tf: dict[str, float] = {}
    for i in range(len(s) - n + 1):
        g = s[i:i + n]
        tf[g] = tf.get(g, 0.0) + 1.0
    norm = math.sqrt(math.fsum(v * v for v in tf.values()))
    if norm == 0:
        return {}
    return {g: v / norm for g, v in tf.items()}


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine of two sparse L2-normalised vectors (iterate the smaller)."""
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    return math.fsum(w * b.get(g, 0.0) for g, w in a.items())


def ngram_rank(records: list[CorpusRecord], query: str, limit: int,
               min_score: float = _NGRAM_NOISE_FLOOR) -> list[tuple[str, float]]:
    """Rank records by char-ngram cosine to the query, dropping below-noise-floor
    matches (shared common trigrams, not a real lexical variant). Ties -> record_id."""
    qv = char_ngram_vector(query)
    scored: list[tuple[str, float]] = []
    for rec in records:
        score = cosine(qv, char_ngram_vector(rec.searchable_text))
        if score >= min_score:
            scored.append((rec.record_id, score))
    scored.sort(key=lambda t: (-t[1], t[0]))
    return scored[:limit]


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = _RRF_K) -> dict[str, float]:
    """RRF: score(d) = sum_i 1/(k + rank_i(d)). rankings are lists of record_ids,
    each already ordered best-first. Deterministic."""
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank_pos, rid in enumerate(ranking, start=1):
            fused[rid] = fused.get(rid, 0.0) + 1.0 / (k + rank_pos)
    return fused


class HybridRanker:
    """BM25 + char-ngram (offline default), optionally + dense embeddings (opt-in).

    ``embed``: optional ``Callable[[list[str]], list[list[float]]]`` returning one
    vector per input string. If bound, a dense-cosine ranking is fused in and the
    method label records that neural embeddings were used. If absent, the ranker is
    fully deterministic/offline and claims no neural semantics.
    """

    def __init__(self, embed: Callable[[list[str]], list[list[float]]] | None = None) -> None:
        self._embed = embed

    @property
    def uses_dense(self) -> bool:
        return self._embed is not None

    def method_label(self) -> str:
        base = "rrf(bm25 + char-ngram-cosine)"
        return f"rrf(bm25 + char-ngram-cosine + dense-embeddings)" if self.uses_dense else base

    def _dense_ranking(self, records: list[CorpusRecord], query: str, limit: int) -> list[str]:
        vecs = self._embed([query] + [r.searchable_text for r in records])
        # Fail closed if the opt-in backend returns the wrong number of vectors: a
        # silent zip()-truncation would re-rank only a prefix of the corpus while still
        # claiming "neural embeddings fused" (confident-tone tool failure).
        if len(vecs) != len(records) + 1:
            raise ValueError(
                f"embed() returned {len(vecs)} vectors for {len(records) + 1} inputs "
                "(query + docs); a dense backend must return one vector per input")
        qv, doc_vs = vecs[0], vecs[1:]

        def _cos(a: list[float], b: list[float]) -> float:
            na = math.sqrt(math.fsum(x * x for x in a)) or 1.0
            nb = math.sqrt(math.fsum(x * x for x in b)) or 1.0
            return math.fsum(x * y for x, y in zip(a, b)) / (na * nb)

        scored = [(r.record_id, _cos(qv, dv)) for r, dv in zip(records, doc_vs)]
        scored.sort(key=lambda t: (-t[1], t[0]))
        return [rid for rid, s in scored[:limit] if s > 0]

    def rank(self, records: list[CorpusRecord], query: str, limit: int = 10) -> dict:
        if not records:
            return {"method": self.method_label(), "hits": [], "uses_dense": self.uses_dense}
        pool_limit = max(limit * 3, 25)
        bm25_hits = rank(records, query, limit=pool_limit)
        bm25_ids = [h.record.record_id for h in bm25_hits]
        ngram_ids = [rid for rid, _ in ngram_rank(records, query, pool_limit)]

        rankings = [bm25_ids, ngram_ids]
        if self.uses_dense:
            rankings.append(self._dense_ranking(records, query, pool_limit))

        fused = reciprocal_rank_fusion(rankings)
        by_id = {r.record_id: r for r in records}
        ordered = sorted(fused.items(), key=lambda t: (-t[1], t[0]))[:limit]
        bm25_set = set(bm25_ids)
        hits = []
        for rid, score in ordered:
            rec = by_id[rid]
            hits.append({
                "record_id": rid,
                "rrf_score": round(score, 6),
                "title": rec.title,
                # surfaced specifically because the vector signal caught it, not BM25:
                "vector_recovered": rid not in bm25_set,
            })
        return {
            "method": self.method_label(),
            "uses_dense": self.uses_dense,
            "hits": hits,
            "note": (
                "offline char-ngram vector fused with BM25 by RRF; "
                + ("neural embeddings ALSO fused (opt-in backend bound)"
                   if self.uses_dense else "no neural embeddings (deterministic/offline)")
            ),
        }
