"""Tests for the deterministic infra-invariant checker (P1-4)."""
from __future__ import annotations

import json
import time
from pathlib import Path

from overmind.infra_invariants import (
    Status,
    check_force_push_disabled,
    check_log_health,
    check_doc_freshness,
    check_oauth_freshness,
    check_judge_engine_config,
    run_all,
    main,
)


# ── force-push ──────────────────────────────────────────────────────


def test_force_push_true_fails(tmp_path: Path):
    home = tmp_path / ".codex"
    home.mkdir()
    (home / "config.toml").write_text(
        "model = 'gpt-5.5'\ngit-always-force-push = true\n", encoding="utf-8"
    )
    r = check_force_push_disabled([home])
    assert r.status is Status.FAIL
    assert r.evidence and "force-push" in r.evidence[0]


def test_force_push_false_ok(tmp_path: Path):
    home = tmp_path / ".codex"
    home.mkdir()
    (home / "config.toml").write_text("git-always-force-push = false\n", encoding="utf-8")
    r = check_force_push_disabled([home])
    assert r.status is Status.OK


def test_force_push_absent_skips(tmp_path: Path):
    r = check_force_push_disabled([tmp_path / "nope"])
    assert r.status is Status.SKIP


def test_force_push_quoted_true_fails(tmp_path: Path):
    home = tmp_path / ".codex"
    home.mkdir()
    (home / "config.toml").write_text('git-always-force-push = "true"\n', encoding="utf-8")
    assert check_force_push_disabled([home]).status is Status.FAIL


# ── log health ──────────────────────────────────────────────────────


def test_log_health_oversized_warns(tmp_path: Path):
    (tmp_path / "STUCK_FAILURES.md").write_text("x" * 5000, encoding="utf-8")
    r = check_log_health([tmp_path], max_bytes=1000)
    assert r.status is Status.WARN
    assert any("cap" in e for e in r.evidence)


def test_log_health_stale_warns(tmp_path: Path):
    p = tmp_path / "sentinel-findings.jsonl"
    p.write_text("{}\n", encoding="utf-8")
    future = time.time() + 30 * 86400  # pretend "now" is 30 days ahead
    r = check_log_health([tmp_path], stale_days=21, now=future)
    assert r.status is Status.WARN


def test_log_health_clean_ok(tmp_path: Path):
    (tmp_path / "STUCK_FAILURES.md").write_text("small", encoding="utf-8")
    r = check_log_health([tmp_path], max_bytes=1024 * 1024)
    assert r.status is Status.OK


def test_log_health_no_logs_skips(tmp_path: Path):
    assert check_log_health([tmp_path]).status is Status.SKIP


# ── doc freshness ───────────────────────────────────────────────────


def test_doc_freshness_stale_warns(tmp_path: Path):
    doc = tmp_path / "LIVE_CONTEXT.md"
    doc.write_text("snapshot", encoding="utf-8")
    r = check_doc_freshness(doc, stale_days=14, now=time.time() + 20 * 86400)
    assert r.status is Status.WARN


def test_doc_freshness_fresh_ok(tmp_path: Path):
    doc = tmp_path / "LIVE_CONTEXT.md"
    doc.write_text("snapshot", encoding="utf-8")
    assert check_doc_freshness(doc, stale_days=14).status is Status.OK


# ── oauth freshness ─────────────────────────────────────────────────


def test_oauth_expired_fails(tmp_path: Path):
    home = tmp_path / ".codex"
    home.mkdir()
    (home / "auth.json").write_text(
        json.dumps({"tokens": {"expires_at": "2020-01-01T00:00:00Z"}}),
        encoding="utf-8",
    )
    r = check_oauth_freshness([home])
    assert r.status is Status.FAIL
    # The token VALUE must never appear in output — only expiry metadata.
    assert all("expires" in e or "expired" in e for e in r.evidence)


def test_oauth_valid_ok(tmp_path: Path):
    home = tmp_path / ".codex"
    home.mkdir()
    (home / "auth.json").write_text(
        json.dumps({"expires_at": "2099-01-01T00:00:00Z"}), encoding="utf-8"
    )
    assert check_oauth_freshness([home]).status is Status.OK


def test_oauth_epoch_seconds(tmp_path: Path):
    home = tmp_path / ".codex"
    home.mkdir()
    (home / "auth.json").write_text(
        json.dumps({"expires": 4102444800}), encoding="utf-8"  # 2100
    )
    assert check_oauth_freshness([home]).status is Status.OK


def test_oauth_absent_skips(tmp_path: Path):
    assert check_oauth_freshness([tmp_path / "nope"]).status is Status.SKIP


# ── judge engine config ─────────────────────────────────────────────


def test_judge_engine_unknown_fails():
    r = check_judge_engine_config({"OVERMIND_JUDGE_ENGINE": "gpt9000"})
    # FAIL if the factory is importable and rejects it; SKIP if not importable.
    assert r.status in (Status.FAIL, Status.SKIP)


def test_judge_engine_unset_ok():
    assert check_judge_engine_config({}).status is Status.OK


# ── runner / CLI ────────────────────────────────────────────────────


def test_run_all_returns_results():
    results = run_all()
    assert len(results) == 5
    assert all(isinstance(r.detail, str) for r in results)


def test_main_json_smoke(capsys):
    code = main(["--json"])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert isinstance(data, list) and len(data) == 5
    assert code in (0, 1)
