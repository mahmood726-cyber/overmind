"""Targeted-verification path filter for nightly_verify.py.

Adds `--projects-from-file <PATH>` so an operator can re-bundle a known
set of paths (e.g. the 21 stale-UNVERIFIED projects) without waiting for
the natural risk-sorted nightly cadence.

Path matching is case-insensitive and slash-agnostic — `C:\\Foo\\Bar`,
`c:/foo/bar`, and `C:\\Foo\\Bar\\` should all match the same project.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make sibling scripts/ importable
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import nightly_verify  # noqa: E402


class _FakeProject:
    """Minimal stand-in for ProjectRecord for select_projects tests."""

    def __init__(self, project_id, name, root_path, risk_profile="medium",
                 test_commands=("python -m pytest -q",), advanced_math_score=0):
        self.project_id = project_id
        self.name = name
        self.root_path = root_path
        self.risk_profile = risk_profile
        self.test_commands = list(test_commands)
        self.advanced_math_score = advanced_math_score


class _FakeDB:
    def __init__(self, projects):
        self._projects = projects

    def list_projects(self):
        return list(self._projects)


def _make_db():
    return _FakeDB([
        _FakeProject("a", "Alpha", r"C:\Models\Alpha", risk_profile="high"),
        _FakeProject("b", "Beta", r"C:\Models\Beta", risk_profile="medium"),
        _FakeProject("c", "Gamma", r"C:\Projects\gamma", risk_profile="medium_high"),
        _FakeProject("d", "Delta", r"C:\Projects\Delta", risk_profile="medium"),
    ])


def test_select_projects_no_filter_returns_all_within_risk_and_limit():
    db = _make_db()
    out = nightly_verify.select_projects(db, "medium", 10)
    assert {p.name for p in out} == {"Alpha", "Beta", "Gamma", "Delta"}


def test_select_projects_with_paths_filter_restricts_to_listed_paths():
    db = _make_db()
    paths_filter = {nightly_verify._normalize_path(r"C:\Models\Alpha"),
                    nightly_verify._normalize_path(r"C:\Projects\Delta")}
    out = nightly_verify.select_projects(db, "medium", 10, paths_filter=paths_filter)
    assert {p.name for p in out} == {"Alpha", "Delta"}


def test_paths_filter_is_case_insensitive_and_slash_agnostic():
    db = _make_db()
    # Mixed case + forward slashes — should still match Alpha
    paths_filter = {nightly_verify._normalize_path("c:/models/alpha"),
                    nightly_verify._normalize_path(r"c:\projects\DELTA\\")}
    out = nightly_verify.select_projects(db, "medium", 10, paths_filter=paths_filter)
    assert {p.name for p in out} == {"Alpha", "Delta"}


def test_paths_filter_overrides_min_risk_floor():
    """If the operator explicitly listed a path, run it even if min_risk would have excluded it."""
    db = _make_db()
    # min_risk=high would normally exclude Beta (medium), but if it's in the filter, run it
    paths_filter = {nightly_verify._normalize_path(r"C:\Models\Beta")}
    out = nightly_verify.select_projects(db, "high", 10, paths_filter=paths_filter)
    assert {p.name for p in out} == {"Beta"}


def test_paths_filter_empty_set_means_no_projects():
    db = _make_db()
    out = nightly_verify.select_projects(db, "medium", 10, paths_filter=set())
    assert out == []


def test_paths_filter_with_unmatched_path_yields_empty(tmp_path):
    db = _make_db()
    paths_filter = {nightly_verify._normalize_path(r"C:\does\not\exist")}
    out = nightly_verify.select_projects(db, "medium", 10, paths_filter=paths_filter)
    assert out == []


def test_load_paths_filter_reads_one_path_per_line(tmp_path):
    f = tmp_path / "paths.txt"
    f.write_text(
        "C:\\Models\\Alpha\n"
        "  c:/projects/delta  \n"
        "\n"
        "# this is a comment, ignore\n"
        "C:\\Models\\Beta\n",
        encoding="utf-8",
    )
    out = nightly_verify.load_paths_filter(f)
    expected = {
        nightly_verify._normalize_path(r"C:\Models\Alpha"),
        nightly_verify._normalize_path(r"C:\Projects\Delta"),
        nightly_verify._normalize_path(r"C:\Models\Beta"),
    }
    assert out == expected


def test_load_paths_filter_missing_file_raises(tmp_path):
    import pytest
    with pytest.raises(FileNotFoundError):
        nightly_verify.load_paths_filter(tmp_path / "nope.txt")


def test_normalize_path_collapses_case_and_slashes():
    assert nightly_verify._normalize_path(r"C:\Foo\Bar") == nightly_verify._normalize_path(r"c:/foo/bar")
    assert nightly_verify._normalize_path(r"C:\Foo\Bar\\") == nightly_verify._normalize_path(r"C:\Foo\Bar")
