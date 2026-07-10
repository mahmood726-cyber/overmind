"""Public memory-recall benchmark (read-only).

Measures the shipped ``MemoryStore`` retrieval path against public long-term
memory benchmarks (LoCoMo, LongMemEval) so our recall is comparable to the
numbers Mem0 / Zep / MemPalace publish — closing GAP #2 of
``docs/PEER-BENCHMARK-2026-07-10.md`` ("no publicly-comparable recall number").

READ-ONLY contract: this package only *calls* the public ``MemoryStore`` API
(``save`` / ``search`` / ``hybrid_search`` / ``semantic_search_memories``). It
does not modify any memory-behaviour code, and it never rewrites the query to
help the retriever (no hand-tuning). Embeddings, when enabled, are populated on
ingest exactly as ``overmind/memory/extractor.py`` does in production.
"""
