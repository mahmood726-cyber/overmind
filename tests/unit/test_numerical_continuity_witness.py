"""Tests for NumericalContinuityWitness."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def _mission_critical_available() -> bool:
    try:
        import mission_critical  # noqa: F401
        return True
    except ImportError:
        return False


_HAS_MC = _mission_critical_available()


def test_no_baseline_no_provenance_passes(tmp_path: Path):
    from overmind.verification.numerical_continuity import NumericalContinuityWitness
    result = NumericalContinuityWitness().run(tmp_path)
    # No files to check => trivial pass (or SKIP if mc missing)
    assert result.verdict in ("PASS", "SKIP")


@pytest.mark.skipif(_HAS_MC, reason="mc IS installed here")
def test_missing_mission_critical_returns_skip(tmp_path: Path):
    from overmind.verification.numerical_continuity import NumericalContinuityWitness
    (tmp_path / "baseline.json").write_text(
        '{"schema_version":"0.1","records":{}}', encoding="utf-8",
    )
    result = NumericalContinuityWitness().run(tmp_path)
    assert result.verdict == "SKIP"
    assert "mission_critical" in result.stderr


@pytest.mark.skipif(not _HAS_MC, reason="needs mission_critical installed")
def test_matching_baseline_report_passes(tmp_path: Path):
    from mission_critical.baseline import BaselineStore
    from overmind.verification.numerical_continuity import NumericalContinuityWitness

    store = BaselineStore(tmp_path / "baseline.json")
    store.record("paper-1", pooled_estimate=-0.223)
    store.save()
    (tmp_path / "paper-1.report.json").write_text(json.dumps({
        "pooled_estimate": -0.223,
    }), encoding="utf-8")

    result = NumericalContinuityWitness().run(tmp_path)
    assert result.verdict == "PASS"


@pytest.mark.skipif(not _HAS_MC, reason="needs mission_critical installed")
def test_baseline_drift_fails(tmp_path: Path):
    from mission_critical.baseline import BaselineStore
    from overmind.verification.numerical_continuity import NumericalContinuityWitness

    store = BaselineStore(tmp_path / "baseline.json")
    store.record("paper-1", pooled_estimate=-0.223)
    store.save()
    # drifted
    (tmp_path / "paper-1.report.json").write_text(json.dumps({
        "pooled_estimate": -0.210,
    }), encoding="utf-8")

    result = NumericalContinuityWitness().run(tmp_path)
    assert result.verdict == "FAIL"
    assert "paper-1" in result.stderr


@pytest.mark.skipif(not _HAS_MC, reason="needs mission_critical installed")
def test_unverified_provenance_fails(tmp_path: Path):
    from mission_critical.provenance import ProvenanceStore
    from overmind.verification.numerical_continuity import NumericalContinuityWitness

    prov = ProvenanceStore(tmp_path / "provenance.json")
    prov.add("NCT00095238", source="paper.pdf:p1", extractor="tool")  # not verified
    prov.save()

    result = NumericalContinuityWitness().run(tmp_path)
    assert result.verdict == "FAIL"
    assert "unverified" in result.stderr.lower()


@pytest.mark.skipif(not _HAS_MC, reason="needs mission_critical installed")
def test_verified_provenance_passes(tmp_path: Path):
    from mission_critical.provenance import ProvenanceStore
    from overmind.verification.numerical_continuity import NumericalContinuityWitness

    prov = ProvenanceStore(tmp_path / "provenance.json")
    prov.add("NCT00095238", source="paper.pdf:p1", extractor="human",
             verified=True)
    prov.save()

    result = NumericalContinuityWitness().run(tmp_path)
    assert result.verdict == "PASS"


@pytest.mark.skipif(not _HAS_MC, reason="needs mission_critical installed")
def test_combined_failure_includes_both(tmp_path: Path):
    """When both baseline drift AND unverified provenance, stderr lists both."""
    from mission_critical.baseline import BaselineStore
    from mission_critical.provenance import ProvenanceStore
    from overmind.verification.numerical_continuity import NumericalContinuityWitness

    store = BaselineStore(tmp_path / "baseline.json")
    store.record("paper-1", pooled_estimate=1.0)
    store.save()
    (tmp_path / "paper-1.report.json").write_text(json.dumps({
        "pooled_estimate": 2.0,
    }), encoding="utf-8")

    prov = ProvenanceStore(tmp_path / "provenance.json")
    prov.add("NCT00001", source="a", extractor="tool")
    prov.save()

    result = NumericalContinuityWitness().run(tmp_path)
    assert result.verdict == "FAIL"
    assert "paper-1" in result.stderr
    assert "unverified" in result.stderr.lower()


@pytest.mark.skipif(not _HAS_MC, reason="needs mission_critical installed")
def test_unwraps_diffmeta_report(tmp_path: Path):
    """Diffmeta-shape report (nested python/r) should be unwrapped."""
    from mission_critical.baseline import BaselineStore
    from overmind.verification.numerical_continuity import NumericalContinuityWitness

    store = BaselineStore(tmp_path / "baseline.json")
    store.record("paper-1", pooled_estimate=-0.223)
    store.save()
    (tmp_path / "paper-1.report.json").write_text(json.dumps({
        "python": {"estimate": -0.223},
        "r": {"estimate": -0.223},
    }), encoding="utf-8")

    result = NumericalContinuityWitness().run(tmp_path)
    assert result.verdict == "PASS"
