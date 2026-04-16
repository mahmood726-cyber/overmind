"""Engine behavior when preflight's only blocker is a missing_baseline.

Prior behavior (pre-2026-04-16): preflight's `missing_baseline` short-circuited
the entire run — engine returned verdict=FAIL with a synthetic "preflight"
witness, never running test_suite or smoke. That inflated the FAIL count in
nightly reports (29/35 yesterday were this class) and masked projects whose
real code was fine.

Desired behavior: `missing_baseline` is a missing-numerical-baseline only.
The engine should run test_suite + smoke normally; the numerical witness
itself already emits SKIP when the baseline file is absent. The arbitrator
then downgrades to UNVERIFIED (per the 2026-04-15 SKIP-as-pass lesson).
Other preflight classes (missing_path, missing_executable, missing_module,
corrupt_baseline) still fail-close.
"""
from __future__ import annotations

from overmind.storage.models import ProjectRecord
from overmind.verification.preflight import PreflightResult
from overmind.verification.scope_lock import WitnessResult
from overmind.verification.truthcert_engine import TruthCertEngine


def _tier3_project(root_path: str) -> ProjectRecord:
    return ProjectRecord(
        project_id="demo-tier3",
        name="demo-tier3",
        root_path=root_path,
        project_type="python_tool",
        stack=["python"],
        risk_profile="high",
        advanced_math_score=15,
        test_commands=["pytest"],
    )


class _StubWitness:
    def __init__(self, verdict: str, witness_type: str) -> None:
        self.verdict = verdict
        self.witness_type = witness_type

    def run(self, *args, **kwargs) -> WitnessResult:  # noqa: ANN002, ANN003
        return WitnessResult(
            witness_type=self.witness_type, verdict=self.verdict, exit_code=0,
            stdout="", stderr="", elapsed=0.1,
        )


def _install_stub_witnesses(engine: TruthCertEngine, test_verdict: str, smoke_verdict: str) -> None:
    engine.test_suite_witness = _StubWitness(test_verdict, "test_suite")
    engine.smoke_witness = _StubWitness(smoke_verdict, "smoke")
    # numerical_witness is the real one — it returns SKIP when the baseline
    # file doesn't exist, which is exactly what we want here.


def _install_stub_preflight(engine: TruthCertEngine, failure_class: str | None) -> None:
    class _Stub:
        def check(self, *args, **kwargs) -> PreflightResult:  # noqa: ANN002, ANN003
            if failure_class is None:
                return PreflightResult(ready=True)
            return PreflightResult(
                ready=False,
                failure_class=failure_class,
                details=[f"stub: {failure_class}"],
            )
    engine.preflight = _Stub()


def test_missing_baseline_preflight_produces_unverified_not_fail(tmp_path):
    """THE REGRESSION GUARD: missing_baseline preflight should run the other
    witnesses and emit UNVERIFIED, not short-circuit to FAIL."""
    project_root = tmp_path / "demo"
    project_root.mkdir()
    (project_root / "analysis.py").write_text("VALUE = 1\n", encoding="utf-8")

    engine = TruthCertEngine(tmp_path / "baselines")
    _install_stub_preflight(engine, failure_class="missing_baseline")
    _install_stub_witnesses(engine, test_verdict="PASS", smoke_verdict="PASS")

    bundle = engine.verify(_tier3_project(str(project_root)))

    assert bundle.verdict == "UNVERIFIED", (
        f"expected UNVERIFIED when missing_baseline is the only preflight issue "
        f"and real witnesses pass, got {bundle.verdict!r} ({bundle.arbitration_reason!r})"
    )
    witness_types = {w.witness_type for w in bundle.witness_results}
    assert "test_suite" in witness_types, "test_suite should have run"
    assert "smoke" in witness_types, "smoke should have run"
    numerical = next((w for w in bundle.witness_results if w.witness_type == "numerical"), None)
    assert numerical is not None and numerical.verdict == "SKIP", (
        "numerical should be present with SKIP verdict"
    )


def test_missing_path_preflight_still_fails_closed(tmp_path):
    """Other preflight classes must NOT be downgraded — missing_path is a real
    blocker (project directory doesn't exist; nothing can run)."""
    project_root = tmp_path / "demo"
    project_root.mkdir()

    engine = TruthCertEngine(tmp_path / "baselines")
    _install_stub_preflight(engine, failure_class="missing_path")
    _install_stub_witnesses(engine, test_verdict="PASS", smoke_verdict="PASS")

    bundle = engine.verify(_tier3_project(str(project_root)))

    assert bundle.verdict == "FAIL"
    assert bundle.failure_class == "missing_path"


def test_corrupt_baseline_preflight_still_fails_closed(tmp_path):
    """corrupt_baseline is a real error (malformed JSON, missing required
    fields) — it means the baseline file exists but is broken. That's
    genuine breakage; the project owner needs to regenerate the file."""
    project_root = tmp_path / "demo"
    project_root.mkdir()

    engine = TruthCertEngine(tmp_path / "baselines")
    _install_stub_preflight(engine, failure_class="corrupt_baseline")
    _install_stub_witnesses(engine, test_verdict="PASS", smoke_verdict="PASS")

    bundle = engine.verify(_tier3_project(str(project_root)))

    assert bundle.verdict == "FAIL"
    assert bundle.failure_class == "corrupt_baseline"


def test_missing_baseline_with_failing_tests_stays_fail_or_reject(tmp_path):
    """If test_suite itself fails, the verdict must NOT become UNVERIFIED —
    UNVERIFIED is specifically 'all ran witnesses passed, numerical couldn't
    run.' A real test failure must surface as REJECT/FAIL."""
    project_root = tmp_path / "demo"
    project_root.mkdir()
    (project_root / "analysis.py").write_text("VALUE = 1\n", encoding="utf-8")

    engine = TruthCertEngine(tmp_path / "baselines")
    _install_stub_preflight(engine, failure_class="missing_baseline")
    _install_stub_witnesses(engine, test_verdict="FAIL", smoke_verdict="PASS")

    bundle = engine.verify(_tier3_project(str(project_root)))

    assert bundle.verdict != "UNVERIFIED", (
        f"a real test failure must not be hidden as UNVERIFIED; got {bundle.verdict!r}"
    )
    assert bundle.verdict in {"FAIL", "REJECT"}
