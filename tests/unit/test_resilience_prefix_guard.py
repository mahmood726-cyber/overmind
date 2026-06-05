"""Regression tests for PreFixRiskChecker's dirty-tree guard.

Overmind appends to a tracked DECISIONS.md in every project it touches. Counting
that (and Python bytecode caches) as "human uncommitted changes" made the
nightly skip ~30 repos Overmind itself had dirtied — they never got verified.
The guard must ignore Overmind's own artifacts and only block on real human edits.
"""
from __future__ import annotations

import subprocess

import pytest

from overmind.verification.resilience import (
    _is_overmind_artifact,
    PreFixRiskChecker,
)


# ─── pure helper ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("line", [
    " M DECISIONS.md",
    "?? DECISIONS.md",
    " M sub/dir/DECISIONS.md",
    "?? __pycache__/mod.cpython-313.pyc",
    " M src/__pycache__/x.pyc",
    "?? build/y.pyo",
    "R  old.md -> DECISIONS.md",
])
def test_overmind_artifacts_ignored(line):
    assert _is_overmind_artifact(line) is True


@pytest.mark.parametrize("line", [
    " M index.html",
    "?? src/new_module.py",
    " M dev/benchmarks/latest_user_flow_smoke_test.json",
    " M DECISIONS_NOTES.md",          # not exactly DECISIONS.md
    "R  DECISIONS.md -> real_doc.md",  # destination is a real file
])
def test_real_changes_not_ignored(line):
    assert _is_overmind_artifact(line) is False


# ─── checker against a real temp git repo ──────────────────────────────────

def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   capture_output=True, text=True)


def _init_repo(path):
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@t.t")
    _git(path, "config", "user.name", "t")
    (path / "DECISIONS.md").write_text("# Overmind Decisions\n", encoding="utf-8")
    (path / "app.py").write_text("x = 1\n", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "init")


def test_dirty_only_decisions_md_is_safe(tmp_path):
    _init_repo(tmp_path)
    # Overmind re-appends to its own log -> tree "dirty" but not a human edit.
    (tmp_path / "DECISIONS.md").write_text(
        "# Overmind Decisions\n\n- entry\n", encoding="utf-8")
    # recent_hours=0 so the "recent human commit" check can't mask the result.
    risk = PreFixRiskChecker(recent_hours=0).check(str(tmp_path))
    assert risk.safe is True, risk.reason


def test_dirty_real_file_blocks(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("x = 2  # human edit\n", encoding="utf-8")
    risk = PreFixRiskChecker(recent_hours=0).check(str(tmp_path))
    assert risk.safe is False
    assert "Dirty working tree" in risk.reason
