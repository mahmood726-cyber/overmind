"""Unit test for overmind.integrations.sentinel_aggregator.collect."""
from __future__ import annotations
from pathlib import Path

from overmind.integrations.sentinel_aggregator import collect


def test_collect_empty_when_no_findings(tmp_path):
    """No STUCK_FAILURES.md anywhere → zero findings."""
    (tmp_path / "r1").mkdir()
    result = collect(discover_repos=lambda: [str(tmp_path / "r1")])
    assert result["total_block"] == 0
    assert result["total_warn"] == 0
    assert result["total_repos_with_findings"] == 0
    assert result["top_rules"] == []


def test_collect_aggregates_stuck_failures(tmp_path):
    """STUCK_FAILURES.md files parse, aggregate by rule + repo, sort descending."""
    r1 = tmp_path / "repo1"
    r1.mkdir()
    (r1 / "STUCK_FAILURES.md").write_text(
        "# STUCK_FAILURES.md\n\n"
        "## [BLOCK] P0-hardcoded-local-path\n"
        "- **Location:** `foo.py:1`\n\n"
        "## [BLOCK] P0-placeholder-hmac\n"
        "- **Location:** `bar.py:5`\n\n"
        "## [WARN] P1-unpopulated-placeholder\n"
        "- **Location:** `baz.py:10`\n",
        encoding="utf-8",
    )

    r2 = tmp_path / "repo2"
    r2.mkdir()
    (r2 / "STUCK_FAILURES.md").write_text(
        "## [BLOCK] P0-hardcoded-local-path\n"
        "- **Location:** `x.py:1`\n",
        encoding="utf-8",
    )

    r3 = tmp_path / "repo3-clean"
    r3.mkdir()  # no STUCK_FAILURES.md

    result = collect(discover_repos=lambda: [str(r1), str(r2), str(r3)])

    assert result["total_block"] == 3  # 2 in r1 + 1 in r2
    assert result["total_warn"] == 1
    assert result["total_repos_with_findings"] == 2  # r3 has no findings

    top_rules = {r["rule_id"]: r["count"] for r in result["top_rules"]}
    assert top_rules["P0-hardcoded-local-path"] == 2
    assert top_rules["P0-placeholder-hmac"] == 1
    assert top_rules["P1-unpopulated-placeholder"] == 1

    # Top repos sorted by BLOCK desc, then WARN desc
    assert result["top_repos"][0]["repo"] == str(r1)
    assert result["top_repos"][0]["block"] == 2
    assert result["top_repos"][1]["repo"] == str(r2)
    assert result["top_repos"][1]["block"] == 1


def test_collect_fails_soft_when_discover_raises():
    """If discover_repos raises, aggregator returns error dict (not crash)."""
    def broken():
        raise RuntimeError("simulated discover failure")

    result = collect(discover_repos=broken)
    assert "error" in result
    assert result["total_block"] == 0
    assert result["total_warn"] == 0


def test_collect_handles_unreadable_stuck_failures(tmp_path, monkeypatch):
    """OSError on read_text is skipped, not propagated."""
    r1 = tmp_path / "unreadable"
    r1.mkdir()
    (r1 / "STUCK_FAILURES.md").write_text("## [BLOCK] X\n", encoding="utf-8")

    # Monkeypatch read_text to raise OSError for STUCK_FAILURES.md
    original_read_text = Path.read_text

    def failing_read(self, *args, **kwargs):
        if self.name == "STUCK_FAILURES.md":
            raise OSError("simulated unreadable")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", failing_read)

    result = collect(discover_repos=lambda: [str(r1)])
    assert result["total_block"] == 0
    assert result["total_repos_with_findings"] == 0


def test_collect_ignores_empty_stuck_failures(tmp_path):
    """A STUCK_FAILURES.md with only the header (no findings) counts as 0."""
    r1 = tmp_path / "header-only"
    r1.mkdir()
    (r1 / "STUCK_FAILURES.md").write_text(
        "# STUCK_FAILURES.md\n\n*Written by Sentinel.*\n",
        encoding="utf-8",
    )

    result = collect(discover_repos=lambda: [str(r1)])
    assert result["total_repos_with_findings"] == 0
