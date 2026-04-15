"""End-to-end contract test: Sentinel writes → Overmind reads.

Unlike `tests/unit/test_sentinel_integration.py` which uses hand-authored
JSONL fixtures (asserting the aggregator's PARSER is correct), this test
uses Sentinel's actual `write_findings()` to produce output — asserting
the integration CONTRACT is intact.

Motivating incident (2026-04-15): Sentinel renamed `review-findings.jsonl`
to `sentinel-findings.jsonl` in commit d23b6a8. The unit tests kept
passing because they used hand-rolled filenames. The aggregator went
7 hours silently dropping WARN findings in the portfolio until a manual
audit caught it (fixed in Overmind commit 3572ac4).

This test prevents recurrence by catching:
  1. Filename renames in Sentinel that Overmind hasn't picked up
  2. Schema changes in the Verdict JSON shape (rule_id renamed, etc.)
  3. Severity enum value changes (e.g. "BLOCK" → "block")

Skips gracefully if Sentinel is not installed (e.g. in a minimal test env).
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path

import pytest

sentinel_writer = pytest.importorskip(
    "sentinel.io.writer", reason="Sentinel package not installed in this env"
)
sentinel_core = pytest.importorskip("sentinel.core")
sentinel_paths = pytest.importorskip("sentinel.io.paths")

from overmind.integrations.sentinel_aggregator import collect  # noqa: E402


def _make_verdict(severity, rule_id: str, idx: int = 0):
    """Build a Verdict via Sentinel's own core types — not a hand-rolled dict."""
    return sentinel_core.Verdict(
        rule_id=rule_id,
        severity=severity,
        repo="C:/test-repo",
        file=f"src/mod_{idx}.py",
        line=10 + idx,
        detail=f"pattern matched on line {idx}",
        fix_hint="fix it",
        source="test.md#section",
        timestamp=datetime(2026, 4, 15, 12, 0, idx, tzinfo=timezone.utc),
    )


def test_contract_block_flows_end_to_end(tmp_path: Path):
    """Sentinel writes a BLOCK → Overmind aggregator counts it."""
    v = _make_verdict(sentinel_core.Severity.BLOCK, "P0-test-block")
    sentinel_writer.write_findings(tmp_path, [v])

    assert (tmp_path / sentinel_paths.BLOCK_JSONL).exists(), (
        f"Sentinel should have written {sentinel_paths.BLOCK_JSONL}. "
        f"If it wrote a different filename, the aggregator constants are out of sync."
    )

    result = collect(discover_repos=lambda: [str(tmp_path)])
    assert result["total_block"] == 1
    assert result["total_warn"] == 0
    rule_ids = {r["rule_id"] for r in result["top_rules"]}
    assert "P0-test-block" in rule_ids


def test_contract_warn_flows_end_to_end(tmp_path: Path):
    """Sentinel writes a WARN → Overmind aggregator counts it.

    This is the exact regression that d23b6a8 → 3572ac4 caught: the WARN
    filename changed, unit tests passed, integration broke silently.
    """
    v = _make_verdict(sentinel_core.Severity.WARN, "P1-test-warn")
    sentinel_writer.write_findings(tmp_path, [v])

    assert (tmp_path / sentinel_paths.WARN_JSONL).exists(), (
        f"Sentinel should have written {sentinel_paths.WARN_JSONL}. "
        f"Overmind's aggregator constants must list this name in "
        f"_WARN_JSONL_NAMES as the primary (first) candidate."
    )

    result = collect(discover_repos=lambda: [str(tmp_path)])
    assert result["total_warn"] == 1, (
        f"Sentinel wrote WARN to {sentinel_paths.WARN_JSONL} but aggregator "
        f"didn't find it. Likely a filename drift between Sentinel and the "
        f"aggregator's _WARN_JSONL_NAMES tuple."
    )
    rule_ids = {r["rule_id"] for r in result["top_rules"]}
    assert "P1-test-warn" in rule_ids


def test_contract_mixed_block_and_warn(tmp_path: Path):
    """Multiple severities in one scan flow through correctly."""
    verdicts = [
        _make_verdict(sentinel_core.Severity.BLOCK, "P0-a", idx=0),
        _make_verdict(sentinel_core.Severity.BLOCK, "P0-b", idx=1),
        _make_verdict(sentinel_core.Severity.WARN, "P1-c", idx=2),
    ]
    sentinel_writer.write_findings(tmp_path, verdicts)

    result = collect(discover_repos=lambda: [str(tmp_path)])
    assert result["total_block"] == 2
    assert result["total_warn"] == 1
    rule_ids = {r["rule_id"] for r in result["top_rules"]}
    assert {"P0-a", "P0-b", "P1-c"} <= rule_ids


def test_contract_filename_constants_agree(tmp_path: Path):
    """Direct assertion that the aggregator's candidate list contains the
    filenames Sentinel currently writes. This is the minimal guard against
    the d23b6a8 regression class: even without running the full pipeline,
    drift is caught statically.
    """
    from overmind.integrations import sentinel_aggregator

    assert sentinel_paths.BLOCK_JSONL in sentinel_aggregator._BLOCK_JSONL_NAMES, (
        f"Sentinel writes BLOCK to {sentinel_paths.BLOCK_JSONL} but aggregator's "
        f"_BLOCK_JSONL_NAMES = {sentinel_aggregator._BLOCK_JSONL_NAMES}"
    )
    assert sentinel_paths.WARN_JSONL in sentinel_aggregator._WARN_JSONL_NAMES, (
        f"Sentinel writes WARN to {sentinel_paths.WARN_JSONL} but aggregator's "
        f"_WARN_JSONL_NAMES = {sentinel_aggregator._WARN_JSONL_NAMES}"
    )
    # Also verify the current name is listed FIRST (preferred over legacy)
    assert sentinel_aggregator._WARN_JSONL_NAMES[0] == sentinel_paths.WARN_JSONL, (
        f"Current WARN name {sentinel_paths.WARN_JSONL} must come first in "
        f"aggregator's preference list, before any legacy names. Currently: "
        f"{sentinel_aggregator._WARN_JSONL_NAMES}"
    )


def test_contract_verdict_schema_keys(tmp_path: Path):
    """Sentinel's JSONL entries must contain a `rule_id` key (what the
    aggregator extracts) and a `severity` key (what it ignores, but is
    documented in the aggregator's schema comment)."""
    import json
    v = _make_verdict(sentinel_core.Severity.BLOCK, "P0-schema-check")
    sentinel_writer.write_findings(tmp_path, [v])

    jsonl = (tmp_path / sentinel_paths.BLOCK_JSONL).read_text(encoding="utf-8")
    records = [json.loads(line) for line in jsonl.strip().split("\n")]
    assert len(records) == 1
    record = records[0]
    assert "rule_id" in record, (
        "Sentinel Verdict.to_dict() must emit 'rule_id' — aggregator key. "
        f"Got: {sorted(record.keys())}"
    )
    assert "severity" in record, (
        "Sentinel Verdict.to_dict() must emit 'severity' — documented in "
        f"aggregator schema. Got: {sorted(record.keys())}"
    )
    assert record["rule_id"] == "P0-schema-check"
