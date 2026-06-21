"""Optional retrieval / embeddings (RAG) layer (design point 2).

Lets agents ground on the repos/papers corpus. **Off by default and fully
optional** — when disabled (or when no local embedding runtime is present) the
retriever is a no-op that returns no context, so nothing in the existing
pipeline breaks if this layer is absent.

Enable with ``OVERMIND_RAG_ENABLED=1``. The default embedder is a
dependency-free deterministic hashing embedder (works everywhere, good enough
for keyword-grounded recall and tests); set ``OVERMIND_EMBED_BACKEND=local`` to
use a local Ollama-style embeddings endpoint (Gemma/Qwen) when one is running.
"""
from __future__ import annotations

from overmind.retrieval.embeddings import (
    Embedder,
    HashingEmbedder,
    LocalEmbedder,
    build_embedder,
)
from overmind.retrieval.vector_store import InMemoryVectorStore, ScoredHit
from overmind.retrieval.retriever import Retriever, is_rag_enabled

__all__ = [
    "Embedder",
    "HashingEmbedder",
    "LocalEmbedder",
    "build_embedder",
    "InMemoryVectorStore",
    "ScoredHit",
    "Retriever",
    "is_rag_enabled",
]
