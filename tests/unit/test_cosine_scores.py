"""The numpy-vectorised cosine in db._cosine_scores must be numerically identical
to looping embeddings.cosine_similarity per row — it is a speed optimisation only,
never a behaviour change to semantic retrieval."""
from __future__ import annotations

from overmind.memory import embeddings
from overmind.storage.db import _cosine_scores


def test_cosine_scores_matches_per_row():
    q = [0.1, -0.2, 0.3, 0.4, -0.5]
    docs = [
        [0.1, -0.2, 0.3, 0.4, -0.5],   # identical -> 1.0
        [-0.1, 0.2, -0.3, -0.4, 0.5],  # opposite -> -1.0
        [0.5, 0.5, 0.5, 0.5, 0.5],
        [1.0, 0.0, 0.0, 0.0, 0.0],
    ]
    fast = _cosine_scores(q, docs)
    slow = [embeddings.cosine_similarity(q, d) for d in docs]
    assert len(fast) == len(slow)
    for a, b in zip(fast, slow):
        assert abs(a - b) < 1e-9


def test_cosine_scores_zero_vector_is_zero():
    # Zero-norm doc must score 0.0, not NaN (matches cosine_similarity guard).
    assert _cosine_scores([1.0, 0.0], [[0.0, 0.0]]) == [0.0]
