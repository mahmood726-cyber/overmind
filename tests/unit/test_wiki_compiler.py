"""Tests for the memory wiki-compiler (P3-b)."""
from __future__ import annotations

from types import SimpleNamespace

from overmind.memory.wiki_compiler import compile_wiki


def _m(mid, scope, mtype, title, content="body", tags=None, links=None, confidence=0.8):
    return SimpleNamespace(memory_id=mid, scope=scope, memory_type=mtype, title=title,
                           content=content, tags=tags or [], linked_memories=links or [],
                           confidence=confidence)


def test_compiles_index_and_scope_pages_with_links(tmp_path):
    mems = [
        _m("m1", "portfolio", "heuristic", "Throttle parallel agents", links=["m2"]),
        _m("m2", "portfolio", "regression", "Empty DataFrame access"),
        _m("m3", "project:e156", "decision", "Pool on log scale"),
    ]
    summary = compile_wiki(mems, tmp_path)

    assert summary["memories"] == 3
    assert summary["links"] == 1
    assert (tmp_path / "index.md").exists()
    assert (tmp_path / "portfolio.md").exists()
    assert (tmp_path / "project-e156.md").exists()

    portfolio = (tmp_path / "portfolio.md").read_text(encoding="utf-8")
    # link from m1 → m2 resolves to m2's title
    assert "[[Empty DataFrame access]]" in portfolio
    # grouped under memory_type headers
    assert "## heuristic" in portfolio
    index = (tmp_path / "index.md").read_text(encoding="utf-8")
    assert "[portfolio](portfolio.md)" in index


def test_empty_memories_still_writes_index(tmp_path):
    summary = compile_wiki([], tmp_path)
    assert summary["memories"] == 0
    assert (tmp_path / "index.md").exists()
