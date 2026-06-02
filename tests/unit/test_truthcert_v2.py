"""Tests for TruthCert v2 overlay: evidence snapshot + rubric scoring."""
from __future__ import annotations

from types import SimpleNamespace

from overmind.verification.truthcert_v2 import (
    assess,
    build_evidence_snapshot,
    bundle_vacuous_pass,
    score_rubric,
)


def test_bundle_vacuous_pass_from_dict():
    assert bundle_vacuous_pass({"verdict": "CERTIFIED",
                                "witness_results": [{"verdict": "SKIP"}]}) is True
    assert bundle_vacuous_pass({"verdict": "CERTIFIED",
                                "witness_results": [{"verdict": "PASS"}]}) is False
    assert bundle_vacuous_pass({"verdict": "FAIL",
                                "witness_results": [{"verdict": "SKIP"}]}) is False


def _w(witness_type, verdict, stdout="", stderr="", exit_code=0, elapsed=0.1):
    return SimpleNamespace(witness_type=witness_type, verdict=verdict, stdout=stdout,
                           stderr=stderr, exit_code=exit_code, elapsed=elapsed)


def _bundle(verdict, witnesses, source_hash="abc123"):
    lock = SimpleNamespace(project_path="C:/Projects/x", source_hash=source_hash)
    return SimpleNamespace(project_id="x-1", scope_lock=lock, witness_results=witnesses,
                           verdict=verdict, bundle_hash="deadbeef", timestamp="2026-06-02T00:00:00Z",
                           signature_method="ed25519")


def _project(ptype="browser_app", math_score=0, rigor="none"):
    return SimpleNamespace(project_type=ptype, advanced_math_score=math_score,
                           advanced_math_rigor=rigor)


def test_clean_when_required_witness_passed():
    b = _bundle("CERTIFIED", [_w("test_suite", "PASS", stdout="12 passed")])
    a = assess(_project("browser_app"), b)
    assert a["assessment"] == "clean"
    assert a["rubric"]["gaps"] == []
    assert a["rubric"]["vacuous_pass"] is False


def test_certified_with_gap_when_required_witness_skipped():
    # browser app certified but the test suite never ran → gap.
    b = _bundle("CERTIFIED", [_w("test_suite", "SKIP", stderr="No test command")])
    a = assess(_project("browser_app"), b)
    assert a["assessment"] == "certified_with_gaps"
    assert "test_suite" in a["rubric"]["gaps"]


def test_vacuous_pass_detected():
    # Pass-like verdict but no PASS witness at all (everything SKIP).
    b = _bundle("PASS", [_w("test_suite", "SKIP"), _w("smoke", "SKIP")])
    r = score_rubric(_project("python_tool"), b)
    assert r["vacuous_pass"] is True


def test_math_heavy_requires_numerical():
    b = _bundle("CERTIFIED", [_w("test_suite", "PASS", stdout="ok"),
                              _w("numerical", "SKIP", stderr="No baseline file")])
    r = score_rubric(_project("r_project", math_score=20, rigor="extreme"), b)
    assert "numerical" in r["required_nonskip"]
    assert "numerical" in r["gaps"]


def test_fail_verdict_is_fail():
    b = _bundle("FAIL", [_w("test_suite", "FAIL", stdout="1 failed")])
    assert assess(_project("python_tool"), b)["assessment"] == "fail"


def test_evidence_snapshot_curates_and_carries_provenance():
    b = _bundle("CERTIFIED", [_w("test_suite", "PASS",
                stdout="collected 12 items\n... noise ...\n12 passed in 0.4s")])
    snap = build_evidence_snapshot(b)
    assert snap["provenance"]["source_hash"] == "abc123"
    assert snap["provenance"]["signed"] is True
    ev = snap["witnesses"][0]["evidence"]
    assert any("passed" in line for line in ev)  # salient line retained
