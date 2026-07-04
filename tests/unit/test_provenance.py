"""Tests for accept-point verdict provenance + the WARN-cycle quantifier
(D7 / D4 / D2). Recording is SHADOW: it must capture posture correctly and
never change a verdict.
"""
from __future__ import annotations

import json

import pytest

from overmind.storage.models import VerificationResult
from overmind.verification.provenance import (
    ProvenanceRecorder,
    VerdictProvenance,
    build_provenance,
    configured_judge_vendors,
    provenance_mode,
    resolve_recorder,
    summarize_file,
    summarize_records,
)


def _vr(task_id, success, completed):
    return VerificationResult(
        task_id=task_id, success=success,
        required_checks=list(completed), completed_checks=list(completed),
        skipped_checks=[], details=[], trace_id=f"tr-{task_id}",
    )


# --- build_provenance -----------------------------------------------------------

def test_build_provenance_objective_gate_present():
    prov = build_provenance(_vr("t1", True, ["build"]), worker_runner="claude", project_id="p")
    assert prov.objective_gate_present is True
    assert prov.would_ship_without_gate is False
    assert prov.worker_runner == "claude"
    assert prov.worker_family == "anthropic"
    assert prov.project_id == "p"
    assert prov.trace_id == "tr-t1"


def test_build_provenance_judge_only_flags():
    prov = build_provenance(_vr("t2", True, ["semantic_requirements"]), worker_runner="codex")
    assert prov.objective_gate_present is False
    assert prov.would_ship_without_gate is True
    assert prov.worker_family == "openai"


def test_build_provenance_cross_vendor_enrichment():
    class _CV:
        present = True
        decorrelated = True
        checker_engine = "codex"
    prov = build_provenance(_vr("t3", True, ["build"]), worker_runner="claude", cross_vendor=_CV())
    assert prov.cross_vendor_present is True
    assert prov.cross_vendor_decorrelated is True
    assert prov.cross_vendor_engine == "codex"


def test_build_provenance_cost_enrichment():
    prov = build_provenance(_vr("t4", True, ["build"]), worker_runner="claude", cost_usd=0.42)
    assert prov.cost_usd == pytest.approx(0.42)


def test_configured_judge_vendors_from_env(monkeypatch):
    monkeypatch.setenv("OVERMIND_JUDGE_ENGINE", "claude, codex, agy")
    fams = configured_judge_vendors()
    assert fams == ["anthropic", "openai", "google"]


def test_configured_judge_vendors_empty(monkeypatch):
    monkeypatch.delenv("OVERMIND_JUDGE_ENGINE", raising=False)
    assert configured_judge_vendors() == []


# --- recorder + mode ------------------------------------------------------------

def test_mode_default_off(monkeypatch):
    monkeypatch.delenv("OVERMIND_PROVENANCE", raising=False)
    assert provenance_mode() == "off"


def test_resolve_recorder_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("OVERMIND_PROVENANCE", raising=False)
    assert resolve_recorder(tmp_path / "p.jsonl") is None


def test_resolve_recorder_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("OVERMIND_PROVENANCE", "shadow")
    rec = resolve_recorder(tmp_path / "p.jsonl")
    assert isinstance(rec, ProvenanceRecorder)


def test_resolve_recorder_path_override(monkeypatch, tmp_path):
    monkeypatch.setenv("OVERMIND_PROVENANCE", "on")
    monkeypatch.setenv("OVERMIND_PROVENANCE_PATH", str(tmp_path / "custom.jsonl"))
    rec = resolve_recorder(tmp_path / "default.jsonl")
    assert rec.jsonl_path.name == "custom.jsonl"


def test_recorder_appends_jsonl(tmp_path):
    path = tmp_path / "sub" / "verdicts.jsonl"
    rec = ProvenanceRecorder(path)
    rec.record(build_provenance(_vr("a", True, ["build"]), worker_runner="claude"))
    rec.record(build_provenance(_vr("b", True, ["semantic_requirements"]), worker_runner="codex"))
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["task_id"] == "a" and first["objective_gate_present"] is True


# --- WARN-cycle quantifier ------------------------------------------------------

def test_summarize_records_tally():
    recs = [
        build_provenance(_vr("a", True, ["build"]), worker_runner="claude").to_dict(),
        build_provenance(_vr("b", True, ["semantic_requirements"]), worker_runner="claude").to_dict(),
        build_provenance(_vr("c", True, ["trajectory_fast_path"]), worker_runner="codex").to_dict(),
        build_provenance(_vr("d", False, ["semantic_requirements"]), worker_runner="claude").to_dict(),
    ]
    s = summarize_records(recs)
    assert s.total == 4
    assert s.successes == 3          # a, b, c
    assert s.with_objective_gate == 1  # a
    assert s.would_ship_without_gate == 2  # b, c
    assert s.pct_success_on_consensus_only == pytest.approx(66.67, abs=0.01)
    assert s.worker_families == {"anthropic": 3, "openai": 1}


def test_summarize_cross_vendor_and_cost():
    class _CV:
        present = True
        decorrelated = True
        checker_engine = "codex"
    recs = [
        build_provenance(_vr("a", True, ["build"]), worker_runner="claude",
                         cross_vendor=_CV(), cost_usd=1.5).to_dict(),
        build_provenance(_vr("b", True, ["build"]), worker_runner="claude", cost_usd=0.5).to_dict(),
    ]
    s = summarize_records(recs)
    assert s.with_cross_vendor == 1
    assert s.decorrelated_cross_vendor == 1
    assert s.total_cost_usd == pytest.approx(2.0)


def test_summarize_empty_pct_is_none():
    s = summarize_records([])
    assert s.pct_success_on_consensus_only is None
    assert "n/a" in s.headline()


def test_summarize_file_roundtrip(tmp_path):
    path = tmp_path / "v.jsonl"
    rec = ProvenanceRecorder(path)
    rec.record(build_provenance(_vr("a", True, ["build"]), worker_runner="claude"))
    rec.record(build_provenance(_vr("b", True, ["semantic_requirements"]), worker_runner="claude"))
    s = summarize_file(path)
    assert s.successes == 2
    assert s.would_ship_without_gate == 1
    assert s.pct_success_on_consensus_only == pytest.approx(50.0)


def test_summarize_file_missing_returns_empty(tmp_path):
    s = summarize_file(tmp_path / "nope.jsonl")
    assert s.total == 0


def test_summarize_file_skips_malformed(tmp_path):
    path = tmp_path / "v.jsonl"
    path.write_text(
        json.dumps(build_provenance(_vr("a", True, ["build"]), worker_runner="claude").to_dict())
        + "\nnot json\n"
        + json.dumps(build_provenance(_vr("b", True, ["semantic_requirements"]), worker_runner="c").to_dict())
        + "\n",
        encoding="utf-8",
    )
    s = summarize_file(path)
    assert s.total == 2  # malformed line skipped


def test_provenance_to_dict_is_json_serializable():
    prov = build_provenance(_vr("a", True, ["build"]), worker_runner="claude")
    json.dumps(prov.to_dict())  # must not raise
