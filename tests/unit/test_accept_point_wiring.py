"""Wiring tests for the Dispatch accept-point instruments (provenance D7 + cost
D5) as attached to the Orchestrator.

The accept-point helper methods reference only ``self.config.data_dir`` and
``self.db.get_runner``, so we exercise them with a lightweight fake ``self`` —
proving the ON path (flags enabled) writes the expected artifacts and that the
default OFF path is a no-op, without constructing a full Orchestrator.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from overmind.core.orchestrator import Orchestrator
from overmind.storage.models import VerificationResult
from overmind.verification.provenance import summarize_file


def _fake_self(tmp_path, runner_type="claude"):
    runner = SimpleNamespace(runner_type=runner_type)
    return SimpleNamespace(
        config=SimpleNamespace(data_dir=tmp_path),
        db=SimpleNamespace(get_runner=lambda rid: runner if rid else None),
        # the real Orchestrator carries this staticmethod; mirror it on the fake
        _cost_accounting_enabled=Orchestrator._cost_accounting_enabled,
    )


def _vr(task_id, success, completed):
    return VerificationResult(
        task_id=task_id, success=success,
        required_checks=list(completed), completed_checks=list(completed),
        skipped_checks=[], details=[], trace_id=f"tr-{task_id}",
    )


# --- cost ledger factory + accept-point cost ------------------------------------

def test_new_cost_ledger_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("OVERMIND_COST_ACCOUNTING", raising=False)
    fs = _fake_self(tmp_path)
    assert Orchestrator._new_cost_ledger(fs) is None


def test_new_cost_ledger_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("OVERMIND_COST_ACCOUNTING", "shadow")
    fs = _fake_self(tmp_path)
    ledger = Orchestrator._new_cost_ledger(fs)
    assert ledger is not None


def test_record_cost_attributes_accept(tmp_path, monkeypatch):
    import json as _json
    monkeypatch.setenv("OVERMIND_COST_ACCOUNTING", "on")
    fs = _fake_self(tmp_path)
    ledger = Orchestrator._new_cost_ledger(fs)
    task = SimpleNamespace(project_id="P", task_id="t1")
    result = _vr("t1", True, ["build"])
    output = [_json.dumps({"total_cost_usd": 0.5})]
    Orchestrator._record_cost(fs, ledger, result, task, output)
    econ = ledger.economics("P")
    assert econ.accepted == 1
    assert econ.measured_usd == pytest.approx(0.5)
    assert econ.cost_per_accepted_change == pytest.approx(0.5)


def test_record_cost_noop_when_ledger_none(tmp_path):
    fs = _fake_self(tmp_path)
    task = SimpleNamespace(project_id="P", task_id="t1")
    # must not raise when disabled (ledger None)
    Orchestrator._record_cost(fs, None, _vr("t1", True, ["build"]), task, ["x"])


def test_emit_cost_summary_flags_below_break_even(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OVERMIND_COST_ACCOUNTING", "on")
    fs = _fake_self(tmp_path)
    ledger = Orchestrator._new_cost_ledger(fs)
    task = SimpleNamespace(project_id="P", task_id="t")
    # 1 accept, 3 rejects => 25% acceptance, below break-even
    Orchestrator._record_cost(fs, ledger, _vr("a", True, ["build"]), task, ["out"])
    for tid in ("b", "c", "d"):
        Orchestrator._record_cost(fs, ledger, _vr(tid, False, ["build"]), task, ["out"])
    Orchestrator._emit_cost_summary(fs, ledger)
    out = capsys.readouterr().out
    assert "[COST]" in out
    assert "below ~50% break-even" in out


def test_emit_cost_summary_noop_when_none(tmp_path):
    fs = _fake_self(tmp_path)
    Orchestrator._emit_cost_summary(fs, None)  # must not raise


# --- accept-point provenance ----------------------------------------------------

def test_record_provenance_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("OVERMIND_PROVENANCE", raising=False)
    fs = _fake_self(tmp_path)
    task = SimpleNamespace(project_id="P", task_id="t")
    evidence = SimpleNamespace(runner_id="r1")
    Orchestrator._record_verdict_provenance(fs, _vr("t", True, ["build"]), task, evidence)
    assert not (tmp_path / "provenance" / "verdicts.jsonl").exists()


def test_record_provenance_writes_and_summarizes(tmp_path, monkeypatch):
    monkeypatch.setenv("OVERMIND_PROVENANCE", "shadow")
    fs = _fake_self(tmp_path, runner_type="codex")
    task = SimpleNamespace(project_id="P", task_id="t")
    evidence = SimpleNamespace(runner_id="r1")
    # one gated success, one judge-only success
    Orchestrator._record_verdict_provenance(fs, _vr("g", True, ["build"]), task, evidence)
    Orchestrator._record_verdict_provenance(
        fs, _vr("j", True, ["semantic_requirements"]), task, evidence
    )
    path = tmp_path / "provenance" / "verdicts.jsonl"
    assert path.exists()
    summary = summarize_file(path)
    assert summary.successes == 2
    assert summary.would_ship_without_gate == 1
    assert summary.worker_families.get("openai") == 2  # codex -> openai
