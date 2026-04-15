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


def test_collect_aggregates_from_jsonl(tmp_path):
    """JSONL is preferred source — parse schema-stable, no regex fragility."""
    import json as _json
    r1 = tmp_path / "repo1"
    r1.mkdir()
    (r1 / "STUCK_FAILURES.jsonl").write_text(
        _json.dumps({"rule_id": "P0-hardcoded-local-path", "severity": "BLOCK"}) + "\n"
        + _json.dumps({"rule_id": "P0-placeholder-hmac", "severity": "BLOCK"}) + "\n",
        encoding="utf-8",
    )
    (r1 / "review-findings.jsonl").write_text(
        _json.dumps({"rule_id": "P1-unpopulated-placeholder", "severity": "WARN"}) + "\n",
        encoding="utf-8",
    )

    r2 = tmp_path / "repo2"
    r2.mkdir()
    (r2 / "STUCK_FAILURES.jsonl").write_text(
        _json.dumps({"rule_id": "P0-hardcoded-local-path", "severity": "BLOCK"}) + "\n",
        encoding="utf-8",
    )

    r3 = tmp_path / "repo3-clean"
    r3.mkdir()

    result = collect(discover_repos=lambda: [str(r1), str(r2), str(r3)])

    assert result["total_block"] == 3
    assert result["total_warn"] == 1
    assert result["total_repos_with_findings"] == 2
    assert all(r["source"] == "jsonl" for r in result["top_repos"])

    top_rules = {r["rule_id"]: r["count"] for r in result["top_rules"]}
    assert top_rules["P0-hardcoded-local-path"] == 2
    assert top_rules["P0-placeholder-hmac"] == 1


def test_collect_falls_back_to_md_when_no_jsonl(tmp_path):
    """Back-compat: repos scanned before the JSONL writer existed still work.

    In practice the Sentinel writer emits BLOCKs to STUCK_FAILURES.md and
    WARNs to review-findings.md — they're separate files, never mixed.
    """
    r1 = tmp_path / "legacy-repo"
    r1.mkdir()
    (r1 / "STUCK_FAILURES.md").write_text(
        "# STUCK_FAILURES.md\n\n"
        "## [BLOCK] P0-hardcoded-local-path\n"
        "- **Location:** `foo.py:1`\n",
        encoding="utf-8",
    )
    (r1 / "review-findings.md").write_text(
        "# review-findings.md\n\n"
        "## [WARN] P1-x\n"
        "- **Location:** `y.py:1`\n",
        encoding="utf-8",
    )

    result = collect(discover_repos=lambda: [str(r1)])
    assert result["total_block"] == 1
    assert result["total_warn"] == 1
    assert result["top_repos"][0]["source"] == "md"


def test_collect_prefers_jsonl_when_both_present(tmp_path):
    """If both JSONL and MD exist in a repo, JSONL wins — MD is legacy."""
    import json as _json
    r1 = tmp_path / "repo"
    r1.mkdir()
    (r1 / "STUCK_FAILURES.jsonl").write_text(
        _json.dumps({"rule_id": "from-jsonl", "severity": "BLOCK"}) + "\n",
        encoding="utf-8",
    )
    (r1 / "STUCK_FAILURES.md").write_text(
        "## [BLOCK] from-md\n- **Location:** `x:1`\n", encoding="utf-8",
    )

    result = collect(discover_repos=lambda: [str(r1)])
    top_rules = {r["rule_id"]: r["count"] for r in result["top_rules"]}
    assert "from-jsonl" in top_rules
    assert "from-md" not in top_rules


def test_collect_skips_malformed_jsonl_lines(tmp_path):
    """Malformed lines must not crash the aggregator."""
    import json as _json
    r1 = tmp_path / "messy-repo"
    r1.mkdir()
    (r1 / "STUCK_FAILURES.jsonl").write_text(
        _json.dumps({"rule_id": "R-1", "severity": "BLOCK"}) + "\n"
        + "not-json-at-all\n"
        + "\n"  # blank
        + '{"missing_rule_id": true}\n'
        + _json.dumps({"rule_id": "R-2", "severity": "BLOCK"}) + "\n",
        encoding="utf-8",
    )

    result = collect(discover_repos=lambda: [str(r1)])
    assert result["total_block"] == 2  # R-1 + R-2, malformed lines skipped


def test_collect_fails_soft_when_discover_raises():
    """If discover_repos raises, aggregator returns error dict (not crash)."""
    def broken():
        raise RuntimeError("simulated discover failure")

    result = collect(discover_repos=broken)
    assert "error" in result
    assert result["total_block"] == 0
    assert result["total_warn"] == 0


def test_collect_handles_unreadable_findings(tmp_path, monkeypatch):
    """OSError on read_text is skipped, not propagated."""
    r1 = tmp_path / "unreadable"
    r1.mkdir()
    (r1 / "STUCK_FAILURES.md").write_text("## [BLOCK] X\n", encoding="utf-8")

    original_read_text = Path.read_text

    def failing_read(self, *args, **kwargs):
        if self.name.startswith("STUCK_FAILURES") or self.name.startswith("review-findings"):
            raise OSError("simulated unreadable")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", failing_read)

    result = collect(discover_repos=lambda: [str(r1)])
    assert result["total_block"] == 0
    assert result["total_repos_with_findings"] == 0


def test_collect_reads_current_warn_filename_jsonl(tmp_path):
    """P0-NEW: Sentinel renamed WARN output from review-findings.* to
    sentinel-findings.* to avoid colliding with the /review skill. Aggregator
    must read the current name or all post-rename WARN findings are lost.
    """
    import json as _json
    r = tmp_path / "fresh-repo"
    r.mkdir()
    (r / "sentinel-findings.jsonl").write_text(
        _json.dumps({"rule_id": "P1-current-warn", "severity": "WARN"}) + "\n",
        encoding="utf-8",
    )

    result = collect(discover_repos=lambda: [str(r)])
    assert result["total_warn"] == 1
    assert "P1-current-warn" in {r["rule_id"] for r in result["top_rules"]}


def test_collect_reads_current_warn_filename_md(tmp_path):
    """Same as above for the MD fallback path."""
    r = tmp_path / "fresh-repo"
    r.mkdir()
    (r / "sentinel-findings.md").write_text(
        "# sentinel-findings.md\n\n## [WARN] P1-current-md\n"
        "- **Location:** `x.py:1`\n",
        encoding="utf-8",
    )

    result = collect(discover_repos=lambda: [str(r)])
    assert result["total_warn"] == 1


def test_collect_prefers_current_warn_name_over_legacy(tmp_path):
    """Mid-migration repo has both filename variants. Current name wins —
    legacy files are stale from before the rename."""
    import json as _json
    r = tmp_path / "mid-migration"
    r.mkdir()
    (r / "sentinel-findings.jsonl").write_text(
        _json.dumps({"rule_id": "P1-fresh", "severity": "WARN"}) + "\n",
        encoding="utf-8",
    )
    (r / "review-findings.jsonl").write_text(
        _json.dumps({"rule_id": "P1-stale", "severity": "WARN"}) + "\n",
        encoding="utf-8",
    )

    result = collect(discover_repos=lambda: [str(r)])
    rule_ids = {r["rule_id"] for r in result["top_rules"]}
    assert "P1-fresh" in rule_ids
    assert "P1-stale" not in rule_ids


def test_collect_top_repos_deterministic_on_ties(tmp_path):
    """P1-5: top_repos ordering must be stable across runs when (block, warn) tie.

    Without a secondary key, Python's stable sort preserves discover_repos()
    iteration order, so the nightly report churns between runs whenever FS
    walk order differs.
    """
    import json as _json
    for name in ["alpha", "beta", "gamma"]:
        r = tmp_path / name
        r.mkdir()
        (r / "STUCK_FAILURES.jsonl").write_text(
            _json.dumps({"rule_id": "R", "severity": "BLOCK"}) + "\n",
            encoding="utf-8",
        )

    forward = [str(tmp_path / n) for n in ["alpha", "beta", "gamma"]]
    reversed_ = [str(tmp_path / n) for n in ["gamma", "beta", "alpha"]]

    result_forward = collect(discover_repos=lambda: forward)
    result_reversed = collect(discover_repos=lambda: reversed_)

    assert result_forward["top_repos"] == result_reversed["top_repos"]
    repo_names = [r["repo"] for r in result_forward["top_repos"]]
    assert repo_names == sorted(repo_names), "tiebreak should be repo path alphabetical"


def test_collect_top_rules_deterministic_on_ties(tmp_path):
    """P1-5: top_rules ordering must be stable when counts tie."""
    import json as _json
    for i, rule in enumerate(["rule-c", "rule-a", "rule-b"]):
        r = tmp_path / f"repo{i}"
        r.mkdir()
        (r / "STUCK_FAILURES.jsonl").write_text(
            _json.dumps({"rule_id": rule, "severity": "BLOCK"}) + "\n",
            encoding="utf-8",
        )

    repos = [str(tmp_path / f"repo{i}") for i in range(3)]
    result = collect(discover_repos=lambda: repos)
    rule_ids = [r["rule_id"] for r in result["top_rules"]]

    assert rule_ids == sorted(rule_ids), "tiebreak should be rule_id alphabetical"


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
