"""Aggregate Sentinel findings across the portfolio.

Used by scripts/nightly_verify.py to include Sentinel findings in the
nightly report. Also callable standalone:

    from overmind.integrations.sentinel_aggregator import collect

Source preference (per repo):
  1. JSONL — canonical, schema-stable. One JSON object per line. Preferred.
  2. MD   — legacy fallback. Parsed by regex.

Filename preference (per severity, within each source):
  BLOCK: STUCK_FAILURES.{jsonl,md}   (stable across Sentinel versions)
  WARN : sentinel-findings.{jsonl,md} (current) → review-findings.{jsonl,md} (legacy)

The WARN rename avoided collision with the `/review` skill. Source of truth
for Sentinel's output names: ``C:/sentinel/sentinel/io/paths.py``. The legacy
names are retained here until the portfolio has been fully re-scanned.

Fails soft: if `push_all_repos` isn't importable (portfolio discovery not
set up), returns an error dict rather than raising. Nightly verify must
not crash because a sibling integration broke.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Callable, Iterable

# Append, not insert-0, so real overmind imports don't get shadowed.
# Resolves via Path.home() (cross-platform); env var override for CI/testing.
import os as _os
_DEFAULT_DISCOVER_IMPORT_ROOT = _os.environ.get(
    "OVERMIND_DISCOVER_IMPORT_ROOT", str(Path.home())
)

_RX_BLOCK = re.compile(r"^## \[BLOCK\] (\S+)", re.MULTILINE)
_RX_WARN = re.compile(r"^## \[WARN\] (\S+)", re.MULTILINE)

# Filename candidates per (severity, format). Ordered preferred → legacy.
# Keep in sync with C:\sentinel\sentinel\io\paths.py:WARN_MD/WARN_JSONL +
# LEGACY_FILENAMES. Drift = silent WARN loss, per commit c7d225f's own bug.
_BLOCK_JSONL_NAMES = ("STUCK_FAILURES.jsonl",)
_BLOCK_MD_NAMES = ("STUCK_FAILURES.md",)
_WARN_JSONL_NAMES = ("sentinel-findings.jsonl", "review-findings.jsonl")
_WARN_MD_NAMES = ("sentinel-findings.md", "review-findings.md")


def _first_existing(root: Path, names: Iterable[str]) -> Path | None:
    for n in names:
        p = root / n
        if p.exists():
            return p
    return None


def _default_discover_repos() -> list[str]:
    """Import push_all_repos.discover_repos from the home dir. Returns empty
    list (plus raises on caller's side? no — we wrap in collect()) if not
    available."""
    if _DEFAULT_DISCOVER_IMPORT_ROOT not in sys.path:
        sys.path.append(_DEFAULT_DISCOVER_IMPORT_ROOT)
    from push_all_repos import discover_repos
    return list(discover_repos())


def _read_jsonl(path: Path) -> list[str]:
    """Extract DEDUPLICATED rule_ids from a Sentinel JSONL log.

    Sentinel's JSONL files are append-only — every scan adds entries without
    rewriting prior ones. A finding that persists across N scans appears N
    times. The 2026-05-06 audit found 9.2x amplification in C:/overmind's
    STUCK_FAILURES.jsonl (3,048 lines / 332 unique findings) and similar
    ratios across the portfolio's largest repos (TruthCert-Validation-Papers,
    E156, ProjectIndex), inflating the nightly's `total_block` from a real
    ~14-18K to a reported ~140K.

    Dedup key: (rule_id, file, line). Repo is implicit (one file = one repo).
    Malformed lines skipped. Tuples missing rule_id are dropped.

    Returns a list of rule_ids — one entry per distinct finding — so callers
    that count by length get the actionable-finding count, not the
    re-recorded-occurrences count.
    """
    rule_ids: list[str] = []
    seen: set[tuple] = set()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return rule_ids
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        rid = obj.get("rule_id")
        if not rid:
            continue
        # Coerce `line` to str so int 42 and str "42" collapse to the SAME
        # bucket. Without this, a Sentinel writer flipping int↔str across
        # versions would silently re-introduce the 9.2x amplification this
        # dedup is meant to prevent. See review-findings-session-2026-05-06.md
        # P1-4 (Software Eng + Test Coverage + Concurrency triple-flagged).
        key = (rid, str(obj.get("file", "")), str(obj.get("line", "")))
        if key in seen:
            continue
        seen.add(key)
        rule_ids.append(rid)
    return rule_ids


def _read_md_regex(path: Path, pattern: re.Pattern) -> list[str]:
    """Legacy MD fallback — parse rule ids via regex."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return pattern.findall(text)


def _read_findings_for_repo(root: Path) -> tuple[list[str], list[str], str]:
    """Return (block_rule_ids, warn_rule_ids, source_label) for one repo.

    Prefers JSONL (schema-stable). Falls back to MD regex parsing for
    back-compat on repos that haven't been scanned since the JSONL writer
    was introduced.
    """
    blocks_jsonl = _first_existing(root, _BLOCK_JSONL_NAMES)
    warns_jsonl = _first_existing(root, _WARN_JSONL_NAMES)
    blocks_md = _first_existing(root, _BLOCK_MD_NAMES)
    warns_md = _first_existing(root, _WARN_MD_NAMES)

    if blocks_jsonl or warns_jsonl:
        blocks = _read_jsonl(blocks_jsonl) if blocks_jsonl else []
        warns = _read_jsonl(warns_jsonl) if warns_jsonl else []
        return blocks, warns, "jsonl"

    if blocks_md or warns_md:
        blocks = _read_md_regex(blocks_md, _RX_BLOCK) if blocks_md else []
        warns = _read_md_regex(warns_md, _RX_WARN) if warns_md else []
        return blocks, warns, "md"

    return [], [], "none"


def collect(
    discover_repos: Callable[[], Iterable[str]] | None = None,
) -> dict:
    """Aggregate STUCK_FAILURES.md across repos returned by discover_repos.

    Args:
        discover_repos: injectable for testing. When None, uses
            push_all_repos.discover_repos (the portfolio-wide default).

    Returns:
        {
            "total_repos_with_findings": int,
            "total_block": int,
            "total_warn": int,
            "top_repos": [{"repo": str, "block": int, "warn": int}],  # top 10
            "top_rules": [{"rule_id": str, "count": int}],              # top 10
        }
        or {"error": "...", "total_block": 0, "total_warn": 0} on failure.
    """
    try:
        repos = list(discover_repos()) if discover_repos else _default_discover_repos()
    except Exception as e:
        return {
            "error": f"discover_repos unavailable: {type(e).__name__}: {e}",
            "total_block": 0,
            "total_warn": 0,
        }

    repo_findings: list[dict] = []
    rule_counts: dict[str, int] = {}
    total_block = 0
    total_warn = 0

    for repo_path in repos:
        root = Path(repo_path)
        blocks, warns, source = _read_findings_for_repo(root)
        if not blocks and not warns:
            continue
        for rid in blocks + warns:
            rule_counts[rid] = rule_counts.get(rid, 0) + 1
        repo_findings.append({
            "repo": str(repo_path),
            "block": len(blocks),
            "warn": len(warns),
            "source": source,
        })
        total_block += len(blocks)
        total_warn += len(warns)

    repo_findings.sort(key=lambda x: (-x["block"], -x["warn"], x["repo"]))
    top_rules = sorted(rule_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10]

    return {
        "total_repos_with_findings": len(repo_findings),
        "total_block": total_block,
        "total_warn": total_warn,
        "top_repos": repo_findings[:10],
        "top_rules": [{"rule_id": r, "count": c} for r, c in top_rules],
    }
