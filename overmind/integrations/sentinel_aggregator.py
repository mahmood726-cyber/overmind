"""Aggregate Sentinel findings across the portfolio.

Used by scripts/nightly_verify.py to include Sentinel findings in the
nightly report. Also callable standalone:

    from overmind.integrations.sentinel_aggregator import collect

Source preference (per repo):
  1. `STUCK_FAILURES.jsonl` / `review-findings.jsonl` — canonical, schema-
     stable. One JSON object per line. Preferred when present.
  2. `STUCK_FAILURES.md` / `review-findings.md` — legacy fallback. Parsed
     by regex (fragile against heading format changes).

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
_DEFAULT_DISCOVER_IMPORT_ROOT = "C:/Users/user"

_RX_BLOCK = re.compile(r"^## \[BLOCK\] (\S+)", re.MULTILINE)
_RX_WARN = re.compile(r"^## \[WARN\] (\S+)", re.MULTILINE)


def _default_discover_repos() -> list[str]:
    """Import push_all_repos.discover_repos from the home dir. Returns empty
    list (plus raises on caller's side? no — we wrap in collect()) if not
    available."""
    if _DEFAULT_DISCOVER_IMPORT_ROOT not in sys.path:
        sys.path.append(_DEFAULT_DISCOVER_IMPORT_ROOT)
    from push_all_repos import discover_repos
    return list(discover_repos())


def _read_jsonl(path: Path) -> list[str]:
    """Extract rule_ids from a Sentinel JSONL log. Malformed lines skipped."""
    rule_ids: list[str] = []
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
        if rid:
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
    blocks_jsonl = root / "STUCK_FAILURES.jsonl"
    warns_jsonl = root / "review-findings.jsonl"
    blocks_md = root / "STUCK_FAILURES.md"
    warns_md = root / "review-findings.md"

    if blocks_jsonl.exists() or warns_jsonl.exists():
        blocks = _read_jsonl(blocks_jsonl) if blocks_jsonl.exists() else []
        warns = _read_jsonl(warns_jsonl) if warns_jsonl.exists() else []
        return blocks, warns, "jsonl"

    if blocks_md.exists() or warns_md.exists():
        blocks = _read_md_regex(blocks_md, _RX_BLOCK) if blocks_md.exists() else []
        warns = _read_md_regex(warns_md, _RX_WARN) if warns_md.exists() else []
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

    repo_findings.sort(key=lambda x: (-x["block"], -x["warn"]))
    top_rules = sorted(rule_counts.items(), key=lambda kv: -kv[1])[:10]

    return {
        "total_repos_with_findings": len(repo_findings),
        "total_block": total_block,
        "total_warn": total_warn,
        "top_repos": repo_findings[:10],
        "top_rules": [{"rule_id": r, "count": c} for r, c in top_rules],
    }
