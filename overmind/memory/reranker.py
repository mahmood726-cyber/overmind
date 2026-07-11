"""Cross-encoder reranker with optional sentence-transformers backend.

A bi-encoder (``embeddings.py``, all-MiniLM-L6-v2) embeds query and document
*independently* and scores them by cosine — fast, but a single vector per text
is a coarse relevance signal, which is why turn-level LoCoMo recall is weak. A
**cross-encoder** instead feeds ``(query, document)`` through one transformer and
reads a joint relevance score, so it ranks the *right* short turn far more
accurately. We use it only to REORDER a small candidate pool that the cheap
bi-encoder already retrieved (retrieve-then-rerank), never to score the whole
corpus.

Cost/footprint (flagged explicitly):
  * Model ``cross-encoder/ms-marco-MiniLM-L-6-v2`` (~80 MB, 6-layer MiniLM).
  * Runs LOCALLY on CPU, no network at read time, no LLM/generation, no tokens.
  * One forward pass per (query, candidate) pair. With a pool of ~50 that is
    ~50 short-sequence CPU inferences per recall (order 10s-100s of ms on CPU),
    incurred ONLY when reranking is explicitly enabled.

When sentence-transformers is absent (or the model can't load), every function
degrades to a no-op that returns the input order unchanged — identical to how
``embeddings.embed`` returns ``None`` and callers fall back. Zero runtime cost
when the backend isn't installed.
"""

from __future__ import annotations

_model = None
_model_load_attempted = False

# Default cross-encoder: small, CPU-friendly, strong on short-passage reranking.
DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def _load_model():
    """Lazy-load the cross-encoder on first use. Cached across calls."""
    global _model, _model_load_attempted
    if _model_load_attempted:
        return _model
    _model_load_attempted = True
    try:
        from sentence_transformers import CrossEncoder

        _model = CrossEncoder(DEFAULT_MODEL)
    except (ImportError, Exception):
        _model = None
    return _model


def is_available() -> bool:
    """Return True if the cross-encoder backend is loaded and ready."""
    return _load_model() is not None


def rerank_scores(query: str, documents: list[str]) -> list[float] | None:
    """Joint relevance score for each (query, document). None if unavailable.

    Higher = more relevant. Scores are raw cross-encoder logits (ms-marco head);
    only their ORDER matters for reranking.
    """
    if not documents:
        return []
    model = _load_model()
    if model is None:
        return None
    pairs = [(query, doc) for doc in documents]
    scores = model.predict(pairs)
    return [float(s) for s in scores]


def rerank(
    query: str,
    candidates: list,
    text_of,
    *,
    top_k: int | None = None,
) -> list:
    """Reorder ``candidates`` by cross-encoder relevance to ``query``.

    ``text_of(candidate) -> str`` extracts the text to score. Returns a new list
    ordered most-relevant-first (truncated to ``top_k`` if given). If the backend
    is unavailable, returns ``candidates`` unchanged (optionally truncated) — the
    caller's original bi-encoder order is preserved, so this is always safe to
    call.
    """
    if not candidates:
        return []
    scores = rerank_scores(query, [text_of(c) for c in candidates])
    if scores is None:
        return candidates[:top_k] if top_k is not None else list(candidates)
    order = sorted(range(len(candidates)), key=lambda i: scores[i], reverse=True)
    ranked = [candidates[i] for i in order]
    return ranked[:top_k] if top_k is not None else ranked
