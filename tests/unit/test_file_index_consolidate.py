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


# ── Temporal validity: valid_from / superseded_by (A5) ──────────────


def test_superseded_fact_not_surfaced_as_current(tmp_path):
    _write(tmp_path / "old.md", "old-fact", "  type: project\n  superseded_by: new-fact\n")
    _write(tmp_path / "new.md", "new-fact", "  type: project\n")
    payload = fi.cmd_recall("fact", k=5, roots=[tmp_path])
    current_slugs = [r["slug"] for r in payload["results"]]
    historical_slugs = [r["slug"] for r in payload["historical"]]
    assert "new-fact" in current_slugs
    assert "old-fact" not in current_slugs
    assert "old-fact" in historical_slugs
    # The historical entry explains why.
    reason = next(r["reason"] for r in payload["historical"] if r["slug"] == "old-fact")
    assert "superseded_by new-fact" in reason


def test_valid_from_in_future_not_current(tmp_path):
    _write(tmp_path / "future.md", "future-fact", "  type: project\n  valid_from: 2999-01-01\n")
    _write(tmp_path / "now.md", "now-fact", "  type: project\n")
    payload = fi.cmd_recall("fact", k=5, roots=[tmp_path])
    current_slugs = [r["slug"] for r in payload["results"]]
    historical_slugs = [r["slug"] for r in payload["historical"]]
    assert "now-fact" in current_slugs
    assert "future-fact" not in current_slugs
    assert "future-fact" in historical_slugs


def test_valid_from_in_past_is_current(tmp_path):
    _write(tmp_path / "active.md", "active-fact", "  type: project\n  valid_from: 2020-01-01\n")
    payload = fi.cmd_recall("fact", k=5, roots=[tmp_path])
    assert "active-fact" in [r["slug"] for r in payload["results"]]


def test_fieldless_files_always_current_backcompat(tmp_path):
    # No valid_from / valid_until / superseded_by → always current.
    _write(tmp_path / "plain.md", "plain-fact", "  type: project\n")
    assert fi.is_current({}) is True
    payload = fi.cmd_recall("fact", k=5, roots=[tmp_path])
    assert "plain-fact" in [r["slug"] for r in payload["results"]]
    assert payload["historical"] == []


def test_is_current_helper_matrix():
    assert fi.is_current({}) is True
    assert fi.is_current({"superseded_by": "x"}) is False
    assert fi.is_current({"superseded_by": "  "}) is True  # blank = not superseded
    assert fi.is_current({"valid_from": "2999-01-01"}) is False
    assert fi.is_current({"valid_from": "2000-01-01"}) is True
    assert fi.is_current({"valid_until": "2000-01-01"}) is False
    assert fi.is_current({"valid_until": "2999-01-01"}) is True
    # Malformed dates are ignored (treated as current, not crash).
    assert fi.is_current({"valid_from": "not-a-date"}) is True
