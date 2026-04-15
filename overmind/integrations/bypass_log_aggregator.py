"""Aggregate the Sentinel bypass log into weekly portfolio visibility.

When a user runs `SENTINEL_BYPASS=1 git push`, Sentinel's pre-push hook
appends to `~/.sentinel-logs/bypass.log` (tab-separated: timestamp,
repo, user). Bypass is a safety valve, not something to monitor
continuously — but enforcement can silently go dark if one repo
bypasses nightly and no one notices.

This aggregator reads the log, counts bypasses in the last N days, and
returns a report suitable for inclusion in Overmind's nightly output
or a weekly review.

Public API:
    collect(log_path=None, window_days=7) -> dict

Returns:
    {
        "window_days": int,
        "total_bypasses": int,
        "repos": [{"repo": str, "count": int, "latest": iso8601 str}],  # sorted
        "by_day": {"YYYY-MM-DD": int, ...},
        "error": str | None,   # present only on unrecoverable failure
    }

Fails soft: missing log → empty result (not an error). Malformed lines
skipped, not raised.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


DEFAULT_LOG_PATH = Path.home() / ".sentinel-logs" / "bypass.log"


def _parse_line(line: str) -> tuple[datetime, str, str] | None:
    """Parse a tab-separated line: timestamp\\trepo\\tuser.

    Sentinel's hook writes:
      $(date -u +%Y-%m-%dT%H:%M:%SZ)\\t$repo\\t$user\\n
    """
    parts = line.rstrip("\n").split("\t")
    if len(parts) < 3:
        return None
    ts_str, repo, user = parts[0], parts[1], parts[2]
    if not ts_str or not repo:
        return None
    # Handle both Z suffix and +00:00
    ts_str = ts_str.replace("Z", "+00:00") if ts_str.endswith("Z") else ts_str
    try:
        ts = datetime.fromisoformat(ts_str)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts, repo, user


def collect(
    log_path: Optional[Path] = None,
    window_days: int = 7,
    now: Optional[datetime] = None,
) -> dict:
    """Aggregate bypasses in the last `window_days` from `log_path`.

    Args:
        log_path: bypass log file. Defaults to ~/.sentinel-logs/bypass.log.
        window_days: lookback window in days.
        now: override for deterministic testing.

    Returns:
        Report dict (see module docstring).
    """
    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)
    path = Path(log_path) if log_path is not None else DEFAULT_LOG_PATH

    result: dict = {
        "window_days": window_days,
        "total_bypasses": 0,
        "repos": [],
        "by_day": {},
        "error": None,
    }

    if not path.is_file():
        return result

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        result["error"] = f"read failed: {e}"
        return result

    repo_counts: Counter = Counter()
    repo_latest: dict[str, datetime] = {}
    by_day: Counter = Counter()
    total = 0

    for line in text.splitlines():
        if not line.strip():
            continue
        parsed = _parse_line(line)
        if parsed is None:
            continue
        ts, repo, _user = parsed
        if ts < cutoff:
            continue
        total += 1
        repo_counts[repo] += 1
        if repo not in repo_latest or ts > repo_latest[repo]:
            repo_latest[repo] = ts
        by_day[ts.strftime("%Y-%m-%d")] += 1

    repos_sorted = [
        {"repo": r, "count": c, "latest": repo_latest[r].isoformat()}
        for r, c in sorted(repo_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    result["total_bypasses"] = total
    result["repos"] = repos_sorted
    result["by_day"] = dict(sorted(by_day.items()))
    return result
