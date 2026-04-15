"""Tests for overmind.integrations.bypass_log_aggregator."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path

from overmind.integrations.bypass_log_aggregator import collect


def _write_log(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_missing_log_returns_empty(tmp_path: Path):
    result = collect(log_path=tmp_path / "nonexistent.log")
    assert result["total_bypasses"] == 0
    assert result["repos"] == []
    assert result["error"] is None


def test_counts_bypasses_within_window(tmp_path: Path):
    now = datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc)
    log = tmp_path / "bypass.log"
    _write_log(log, [
        # 2 days ago — counted
        f"{(now - timedelta(days=2)).isoformat()}\tC:/repo1\tuser",
        # 1 day ago — counted
        f"{(now - timedelta(days=1)).isoformat()}\tC:/repo1\tuser",
        f"{(now - timedelta(days=1)).isoformat()}\tC:/repo2\tuser",
        # 30 days ago — outside 7-day window
        f"{(now - timedelta(days=30)).isoformat()}\tC:/repo1\tuser",
    ])
    result = collect(log_path=log, window_days=7, now=now)
    assert result["total_bypasses"] == 3
    assert len(result["repos"]) == 2
    assert result["repos"][0] == {
        "repo": "C:/repo1",
        "count": 2,
        "latest": (now - timedelta(days=1)).isoformat(),
    }


def test_sorted_by_count_desc_then_repo_alpha(tmp_path: Path):
    """Top offenders first; alphabetical tiebreak for determinism."""
    now = datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc)
    log = tmp_path / "bypass.log"
    ts = (now - timedelta(hours=1)).isoformat()
    _write_log(log, [
        f"{ts}\tC:/gamma\tuser",  # 1
        f"{ts}\tC:/alpha\tuser",  # 2
        f"{ts}\tC:/alpha\tuser",
        f"{ts}\tC:/beta\tuser",   # 2
        f"{ts}\tC:/beta\tuser",
    ])
    result = collect(log_path=log, now=now)
    repo_order = [r["repo"] for r in result["repos"]]
    # alpha and beta tied at 2 (alpha wins alphabetical); gamma last at 1
    assert repo_order == ["C:/alpha", "C:/beta", "C:/gamma"]


def test_by_day_bucketing(tmp_path: Path):
    now = datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc)
    log = tmp_path / "bypass.log"
    _write_log(log, [
        f"{(now - timedelta(days=1, hours=2)).isoformat()}\tC:/r\tu",
        f"{(now - timedelta(days=1, hours=5)).isoformat()}\tC:/r\tu",
        f"{(now - timedelta(days=2, hours=1)).isoformat()}\tC:/r\tu",
    ])
    result = collect(log_path=log, now=now)
    assert result["by_day"] == {
        (now - timedelta(days=2)).strftime("%Y-%m-%d"): 1,
        (now - timedelta(days=1)).strftime("%Y-%m-%d"): 2,
    }


def test_malformed_lines_skipped(tmp_path: Path):
    now = datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc)
    log = tmp_path / "bypass.log"
    ts = (now - timedelta(hours=1)).isoformat()
    _write_log(log, [
        f"{ts}\tC:/repo1\tuser",   # valid
        "not-a-log-line",          # malformed — skipped
        "\t\t",                    # empty fields — skipped
        f"not-a-timestamp\tC:/r\tu",  # bad ts — skipped
        "",                        # blank — skipped
        f"{ts}\tC:/repo2\tuser",   # valid
    ])
    result = collect(log_path=log, now=now)
    assert result["total_bypasses"] == 2


def test_handles_Z_timestamp_suffix(tmp_path: Path):
    """Sentinel hook uses `date -u +%Y-%m-%dT%H:%M:%SZ` which emits Z
    suffix. fromisoformat didn't accept Z before Python 3.11; we
    translate."""
    now = datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc)
    log = tmp_path / "bypass.log"
    _write_log(log, [
        "2026-04-14T10:00:00Z\tC:/repo\tuser",
    ])
    result = collect(log_path=log, now=now)
    assert result["total_bypasses"] == 1
    assert result["repos"][0]["latest"] == "2026-04-14T10:00:00+00:00"


def test_fails_soft_on_unreadable_log(tmp_path: Path, monkeypatch):
    log = tmp_path / "bypass.log"
    log.write_text("will-not-be-read", encoding="utf-8")

    def failing_read(self, *args, **kwargs):
        if self == log:
            raise OSError("simulated")
        return ""

    monkeypatch.setattr(Path, "read_text", failing_read)
    result = collect(log_path=log)
    assert result["error"] is not None
    assert "read failed" in result["error"]
    assert result["total_bypasses"] == 0


def test_zero_bypasses_is_normal(tmp_path: Path):
    """Empty or all-outside-window log → 0 bypasses, no error."""
    now = datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc)
    log = tmp_path / "bypass.log"
    _write_log(log, [
        f"{(now - timedelta(days=30)).isoformat()}\tC:/old\tu",
    ])
    result = collect(log_path=log, window_days=7, now=now)
    assert result["total_bypasses"] == 0
    assert result["error"] is None
