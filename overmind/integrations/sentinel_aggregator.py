"""Aggregate Sentinel `STUCK_FAILURES.md` files across the portfolio.

Used by scripts/nightly_verify.py to include Sentinel findings in the
nightly report. Also callable standalone:

    from overmind.integrations.sentinel_aggregator import collect

Fails soft: if `push_all_repos` isn't importable (portfolio discovery not
set up), returns an error dict rather than raising. Nightly verify must
not crash because a sibling integration broke.
"""
from __future__ import annotations

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
        sf = Path(repo_path) / "STUCK_FAILURES.md"
        if not sf.exists():
            continue
        try:
            text = sf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        blocks = _RX_BLOCK.findall(text)
        warns = _RX_WARN.findall(text)
        if not blocks and not warns:
            continue
        for rid in blocks + warns:
            rule_counts[rid] = rule_counts.get(rid, 0) + 1
        repo_findings.append({
            "repo": str(repo_path),
            "block": len(blocks),
            "warn": len(warns),
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
