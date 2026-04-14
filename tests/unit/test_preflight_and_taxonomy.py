"""Tests for the preflight gate, failure taxonomy, and CertBundle.failure_class."""
from __future__ import annotations

import json

from overmind.verification.failure_taxonomy import (
    FAILURE_CLASSES,
    classify_bundle,
    classify_witness_failure,
)
from overmind.verification.preflight import PreflightChecker
from overmind.verification.scope_lock import WitnessResult


# ── Preflight ──────────────────────────────────────────────────────


def test_preflight_fails_when_root_path_missing(tmp_path):
    result = PreflightChecker().check(
        root_path=str(tmp_path / "does-not-exist"),
        test_command="pytest",
    )
    assert result.ready is False
    assert result.failure_class == "missing_path"


def test_preflight_fails_when_test_command_executable_not_on_path(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "")
    result = PreflightChecker().check(
        root_path=str(tmp_path),
        test_command="definitely-not-a-real-command-xyz",
    )
    assert result.ready is False
    assert result.failure_class == "missing_executable"


def test_preflight_fails_when_smoke_module_does_not_resolve(tmp_path):
    result = PreflightChecker().check(
        root_path=str(tmp_path),
        test_command="python",
        smoke_modules=("py:nonexistent.module",),
        tier=2,
    )
    assert result.ready is False
    assert result.failure_class == "missing_module"


def test_preflight_fails_when_tier3_baseline_missing(tmp_path):
    result = PreflightChecker().check(
        root_path=str(tmp_path),
        test_command="python",
        tier=3,
        baseline_path=str(tmp_path / "absent.json"),
    )
    assert result.ready is False
    assert result.failure_class == "missing_baseline"


def test_preflight_fails_on_corrupt_baseline(tmp_path):
    baseline = tmp_path / "b.json"
    baseline.write_text("{not json", encoding="utf-8")
    result = PreflightChecker().check(
        root_path=str(tmp_path),
        test_command="python",
        tier=3,
        baseline_path=str(baseline),
    )
    assert result.ready is False
    assert result.failure_class == "corrupt_baseline"


def test_preflight_passes_for_well_formed_tier3(tmp_path):
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")

    baseline = tmp_path / "b.json"
    baseline.write_text(
        json.dumps({"command": "python -c print(1)", "values": {"x": 1}}),
        encoding="utf-8",
    )

    result = PreflightChecker().check(
        root_path=str(tmp_path),
        test_command="python",
        smoke_modules=("py:mypkg",),
        baseline_path=str(baseline),
        tier=3,
    )
    assert result.ready is True
    assert result.failure_class is None
    assert result.checked["root_path"] is True
    assert result.checked["smoke_modules"] is True
    assert result.checked["baseline"] is True


# ── Failure taxonomy ────────────────────────────────────────────────


def _witness(verdict: str, stderr: str = "", witness_type: str = "test_suite", stdout: str = "") -> WitnessResult:
    return WitnessResult(
        witness_type=witness_type, verdict=verdict, exit_code=-1 if verdict == "FAIL" else 0,
        stdout=stdout, stderr=stderr, elapsed=0.0,
    )


def test_classify_witness_failure_detects_reparse_point():
    w = _witness("FAIL", stderr="OSError: [WinError 1920] The file cannot be accessed by the system")
    assert classify_witness_failure(w) == "reparse_point"


def test_classify_witness_failure_detects_import_error():
    w = _witness("FAIL", witness_type="smoke", stderr="ModuleNotFoundError: No module named 'pandas'")
    assert classify_witness_failure(w) == "import_error"


def test_classify_witness_failure_detects_missing_executable():
    w = _witness("FAIL", stderr="[WinError 2] The system cannot find the file specified")
    assert classify_witness_failure(w) == "missing_executable"


def test_classify_witness_failure_detects_timeout():
    w = _witness("FAIL", stderr="Timed out after 120s")
    assert classify_witness_failure(w) == "timeout"


def test_classify_witness_failure_detects_capacity():
    w = _witness("FAIL", stderr="Model provider at capacity; too many requests")
    assert classify_witness_failure(w) == "agent_capacity"


def test_classify_witness_failure_maps_skip_to_missing_baseline():
    w = _witness("SKIP", witness_type="numerical", stderr="No baseline file")
    assert classify_witness_failure(w) == "missing_baseline"


def test_classify_bundle_prefers_specific_over_unknown():
    witnesses = [
        _witness("FAIL", stderr="some unknown stack"),
        _witness("FAIL", witness_type="smoke",
                 stderr="ModuleNotFoundError: No module named 'x'"),
    ]
    assert classify_bundle(witnesses) == "import_error"


def test_classify_bundle_preflight_wins():
    witnesses = [_witness("FAIL", stderr="Timed out after 120s")]
    assert classify_bundle(witnesses, preflight_class="missing_path") == "missing_path"


def test_failure_classes_contains_expected_keys():
    expected = {
        "missing_baseline", "missing_module", "missing_path",
        "missing_executable", "timeout", "reparse_point",
        "import_error", "policy_blocked", "nondeterministic",
    }
    assert expected <= set(FAILURE_CLASSES)
