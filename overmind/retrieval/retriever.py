"""RAG retriever — indexes a text corpus and returns grounding snippets.

Gated by ``OVERMIND_RAG_ENABLED`` (default OFF). When disabled, ``retrieve``
returns an empty list and ``index_paths`` is a no-op, so any caller that wires
this in degrades to "no extra context" rather than breaking.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from overmind.retrieval.embeddings import Embedder, build_embedder
from overmind.retrieval.vector_store import InMemoryVectorStore, ScoredHit

_DEFAULT_EXTS = (".md", ".txt", ".py", ".rst")
_FLAG = "OVERMIND_RAG_ENABLED"


def is_rag_enabled() -> bool:
    return os.environ.get(_FLAG, "").strip().lower() in {"1", "true", "yes", "on"}


def _chunk(text: str, max_chars: int = 800) -> list[str]:
    """Paragraph-ish chunking with a hard char cap; deterministic."""
    chunks: list[str] = []
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if len(para) <= max_chars:
            chunks.append(para)
        else:
            for i in range(0, len(para), max_chars):
                chunks.append(para[i : i + max_chars])
    return chunks


class Retriever:
    """Embed a corpus into an in-memory store and retrieve top-k snippets.

    ``enabled`` defaults to the env flag, but can be forced (e.g. True in tests)
    independently of the global flag.
    """

    def __init__(
        self,
        embedder: Embedder | None = None,
        store: InMemoryVectorStore | None = None,
        enabled: bool | None = None,
        max_chars: int = 800,
    ) -> None:
        self.enabled = is_rag_enabled() if enabled is None else enabled
        self.embedder = embedder or build_embedder()
        self.store = store or InMemoryVectorStore()
        self.max_chars = max_chars

    def index_text(self, doc_id: str, text: str, metadata: dict | None = None) -> int:
        if not self.enabled:
            return 0
        n = 0
        for i, chunk in enumerate(_chunk(text, self.max_chars)):
            self.store.add(
                f"{doc_id}#{i}", self.embedder.embed(chunk), chunk,
                {**(metadata or {}), "source": doc_id},
            )
            n += 1
        return n

    def index_paths(self, paths: Iterable[Path], exts: tuple[str, ...] = _DEFAULT_EXTS) -> int:
        if not self.enabled:
            return 0
        total = 0
        for path in paths:
            path = Path(path)
            files = [path] if path.is_file() else (
                [p for p in path.rglob("*") if p.suffix.lower() in exts] if path.is_dir() else []
            )
            for f in files:
                if f.suffix.lower() not in exts:
                    continue
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                total += self.index_text(str(f), text)
        return total

    def retrieve(self, query: str, k: int = 5) -> list[ScoredHit]:
        if not self.enabled:
            return []
        return self.store.search(self.embedder.embed(query), k=k)
