"""Integration: confirm TruthCertEngine invokes NumericalContinuityWitness
for tier>=3 projects.

Builds a minimal tier-3 project (high risk + advanced-math), runs
verify(), and asserts the witness result list contains a
`numerical_continuity` entry. Does not require R/metafor (the witness
SKIPs gracefully when mission_critical is missing or nothing to check).
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def engine(tmp_path):
    from overmind.verification.truthcert_engine import TruthCertEngine
    return TruthCertEngine(baselines_dir=tmp_path / "baselines")


def _tier3_project(tmp_path: Path):
    """Minimal tier-3 ProjectRecord (high risk + advanced-math)."""
    from overmind.storage.models import ProjectRecord
    project_root = tmp_path / "demo_paper"
    project_root.mkdir()
    # Preflight needs test_command to exist; give it a no-op.
    (project_root / "analysis.py").write_text("x = 1\n", encoding="utf-8")
    return ProjectRecord(
        project_id="demo-paper",
        name="demo-paper",
        root_path=str(project_root),
        risk_profile="high",
        advanced_math_score=15,  # high -> tier 3
        test_commands=["python -c \"pass\""],
    )


def test_tier3_project_gets_numerical_continuity_witness(engine, tmp_path: Path):
    project = _tier3_project(tmp_path)
    bundle = engine.verify(project)
    witness_types = [r.witness_type for r in bundle.witness_results]
    assert "numerical_continuity" in witness_types, (
        f"tier-3 project should include numerical_continuity witness; "
        f"got {witness_types}"
    )


def test_numerical_continuity_skips_when_no_baseline_no_provenance(engine, tmp_path: Path):
    """No baseline.json + no provenance.json + mc installed => PASS
    (nothing to check, nothing failed)."""
    project = _tier3_project(tmp_path)
    bundle = engine.verify(project)
    nc = next((r for r in bundle.witness_results
               if r.witness_type == "numerical_continuity"), None)
    assert nc is not None
    # PASS if mc installed (nothing to check), SKIP if not installed
    assert nc.verdict in ("PASS", "SKIP")


def test_numerical_continuity_fails_on_drift(engine, tmp_path: Path):
    """Seed a baseline.json + drifted report, assert the witness reports FAIL."""
    try:
        from mission_critical.baseline import BaselineStore
    except ImportError:
        pytest.skip("mission_critical not installed")

    project = _tier3_project(tmp_path)
    project_root = Path(project.root_path)
    store = BaselineStore(project_root / "baseline.json")
    store.record("demo-paper", pooled_estimate=-0.223)
    store.save()
    # drifted report
    (project_root / "demo-paper.report.json").write_text(
        '{"pooled_estimate": -0.20}', encoding="utf-8",
    )

    bundle = engine.verify(project)
    nc = next((r for r in bundle.witness_results
               if r.witness_type == "numerical_continuity"), None)
    assert nc is not None
    assert nc.verdict == "FAIL", (
        f"baseline drift should fail; got {nc.verdict} stderr={nc.stderr!r}"
    )
