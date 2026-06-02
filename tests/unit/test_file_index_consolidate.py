"""Tests for markdown-memory consolidation/decay (P2-b).

archive_stale moves expired (valid_until past) facts into archive/ — reversible,
never deletes, never touches undated/fresh facts.
"""
from __future__ import annotations

from pathlib import Path

from overmind.memory import file_index as fi


def _write(p: Path, name: str, frontmatter: str) -> None:
    p.write_text(f"---\nname: {name}\ndescription: d\nmetadata:\n{frontmatter}---\nbody\n",
                 encoding="utf-8")


def test_archives_expired_keeps_others(tmp_path):
    _write(tmp_path / "expired.md", "expired-fact", "  type: project\n  valid_until: 2020-01-01\n")
    _write(tmp_path / "nodate.md", "nodate-fact", "  type: project\n")
    archived = fi.archive_stale(roots=[tmp_path], stale_days=365)
    assert [a["slug"] for a in archived] == ["expired-fact"]
    assert (tmp_path / "archive" / "expired.md").exists()
    assert (tmp_path / "expired.md").exists() is False
    assert (tmp_path / "nodate.md").exists()  # undated is NOT archived


def test_archived_doc_leaves_live_index(tmp_path):
    _write(tmp_path / "expired.md", "expired-fact", "  type: project\n  valid_until: 2020-01-01\n")
    fi.archive_stale(roots=[tmp_path], stale_days=365)
    slugs = [d.slug for d in fi.load_docs([tmp_path])]
    assert "expired-fact" not in slugs  # archive/ is excluded from the live index


def test_consolidate_apply_noop_reports_cleanly(tmp_path):
    _write(tmp_path / "nodate.md", "nodate-fact", "  type: project\n")
    report = fi.cmd_consolidate(roots=[tmp_path], apply=True)
    assert report["archived"] == []
    assert "nothing expired or stale" in report["note"]
