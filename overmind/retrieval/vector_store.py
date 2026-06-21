"""Tiny in-memory cosine-similarity vector store for the optional RAG layer.

Dependency-free. Vectors are assumed L2-normalised by the embedder, so cosine
similarity reduces to a dot product. Suitable for grounding over a few thousand
chunks; not a production ANN index (kept deliberately small + auditable).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ScoredHit:
    doc_id: str
    score: float
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class _Entry:
    doc_id: str
    vector: list[float]
    text: str
    metadata: dict


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._entries: list[_Entry] = []

    def __len__(self) -> int:
        return len(self._entries)

    def add(self, doc_id: str, vector: list[float], text: str, metadata: dict | None = None) -> None:
        self._entries.append(_Entry(doc_id, vector, text, metadata or {}))

    def clear(self) -> None:
        self._entries.clear()

    def search(self, query_vector: list[float], k: int = 5) -> list[ScoredHit]:
        if not self._entries or k <= 0:
            return []
        scored = [
            ScoredHit(e.doc_id, _dot(query_vector, e.vector), e.text, e.metadata)
            for e in self._entries
        ]
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:k]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
