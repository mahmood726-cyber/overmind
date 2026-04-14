"""Tests for auto-baseline probe, regression witness, and related helpers."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from overmind.verification.witnesses import NumericalWitness, RegressionWitness


# ── Auto-baseline probe ────────────────────────────────────────────


def test_numerical_probe_writes_proposed_baseline(tmp_path):
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import json\n"
        "print(json.dumps({'score': 1.5, 'n': 100}))\n",
        encoding="utf-8",
    )
    proposed_dir = tmp_path / "proposed"

    witness = NumericalWitness(timeout=10, proposed_baselines_dir=proposed_dir)
    result = witness.probe_and_propose(
        project_id="demo-project",
        probe_command=f'"{sys.executable}" "{probe}"',
        cwd=str(tmp_path),
    )

    assert result.verdict == "SKIP"
    proposed_path = proposed_dir / "demo-project.json"
    assert proposed_path.exists()
    payload = json.loads(proposed_path.read_text(encoding="utf-8"))
    assert payload["proposed"] is True
    assert payload["values"] == {"score": 1.5, "n": 100}


def test_numerical_probe_skips_without_proposed_dir(tmp_path):
    witness = NumericalWitness(timeout=5)
    result = witness.probe_and_propose(
        project_id="x", probe_command=f'"{sys.executable}" -c "print({{}})"', cwd=str(tmp_path),
    )
    assert result.verdict == "SKIP"
    assert "No proposed_baselines_dir" in result.stderr


def test_numerical_probe_does_not_auto_promote_to_baselines(tmp_path):
    """Auto-proposed baselines must never land in data/baselines/ directly —
    user must move the file explicitly. Enforces the evidence discipline."""
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import json; print(json.dumps({'v': 1}))\n", encoding="utf-8",
    )
    baselines = tmp_path / "baselines"
    proposed = tmp_path / "proposed"
    baselines.mkdir()

    witness = NumericalWitness(timeout=5, proposed_baselines_dir=proposed)
    witness.probe_and_propose(
        project_id="px", probe_command=f'"{sys.executable}" "{probe}"', cwd=str(tmp_path),
    )

    assert (proposed / "px.json").exists()
    assert not (baselines / "px.json").exists()


# ── Regression witness ────────────────────────────────────────────


def test_regression_witness_skips_non_git_project(tmp_path):
    witness = RegressionWitness(timeout=10)
    result = witness.run(f'"{sys.executable}" -c "print(1)"', str(tmp_path))
    assert result.verdict == "SKIP"
    assert "Not a git" in result.stderr


def test_regression_witness_skips_when_prior_ref_missing(tmp_path):
    # Initialise a repo but don't create the ref we reference.
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@test"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, capture_output=True)

    witness = RegressionWitness(timeout=10)
    result = witness.run(
        f'"{sys.executable}" -c "print(1)"', str(tmp_path), prior_ref="does-not-exist",
    )
    assert result.verdict == "SKIP"
    assert "not found" in result.stderr


def test_regression_witness_count_failures_parses_pytest_summary():
    output = (
        "============================= test session starts =============================\n"
        "collected 5 items\n\n"
        "tests/test_a.py ..F.F                                                    [100%]\n\n"
        "============================== 2 failed, 3 passed in 0.04s ====================\n"
    )
    assert RegressionWitness._count_failures(output) == 2


def test_regression_witness_count_failures_zero_when_all_passed():
    output = "===== 10 passed in 0.05s =====\n"
    assert RegressionWitness._count_failures(output) == 0


def test_regression_witness_count_failures_none_when_unparseable():
    output = "no pytest summary here"
    assert RegressionWitness._count_failures(output) is None
