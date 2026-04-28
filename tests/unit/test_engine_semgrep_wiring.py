"""Tests for SemgrepWitness wiring into TruthCertEngine.

Wires the standalone SemgrepWitness (added in 468302a) into the engine's
verify() flow. SemgrepWitness fires at tier 2+ (alongside SmokeWitness)
because tier 1 is "low risk" by design and shouldn't pay the security-scan
cost; tier 2+ are projects where security regressions matter.

Verdict interaction with Arbitrator (existing logic in cert_bundle.py):
  - All non-SKIP witnesses PASS                  -> CERTIFIED
  - Semgrep FAIL + other witnesses PASS          -> REJECT (disagree)
  - Semgrep SKIP (no binary) + others PASS       -> CERTIFIED
                                                   (semgrep SKIP is not
                                                    blocking; only numerical
                                                    SKIP triggers UNVERIFIED)
"""
from __future__ import annotations

from overmind.storage.models import ProjectRecord
from overmind.verification.preflight import PreflightResult
from overmind.verification.scope_lock import WitnessResult
from overmind.verification.truthcert_engine import TruthCertEngine


# ── shared stub helpers ───────────────────────────────────────────────


class _StubWitness:
    def __init__(self, verdict: str, witness_type: str) -> None:
        self.verdict = verdict
        self.witness_type = witness_type

    def run(self, *args, **kwargs) -> WitnessResult:
        return WitnessResult(
            witness_type=self.witness_type, verdict=self.verdict, exit_code=0,
            stdout="", stderr="", elapsed=0.1,
        )


def _install_stubs(
    engine: TruthCertEngine,
    test_v: str = "PASS",
    smoke_v: str = "PASS",
    semgrep_v: str = "PASS",
) -> None:
    engine.test_suite_witness = _StubWitness(test_v, "test_suite")
    engine.smoke_witness = _StubWitness(smoke_v, "smoke")
    engine.semgrep_witness = _StubWitness(semgrep_v, "semgrep")


def _force_preflight_ok(engine: TruthCertEngine) -> None:
    class _OK:
        def check(self, *args, **kwargs) -> PreflightResult:
            return PreflightResult(ready=True)
    engine.preflight = _OK()


def _tier1_project(root_path: str) -> ProjectRecord:
    return ProjectRecord(
        project_id="tier1-demo", name="tier1-demo", root_path=root_path,
        project_type="python_tool", stack=["python"],
        risk_profile="low", advanced_math_score=0,
        test_commands=["pytest"],
    )


def _tier2_project(root_path: str) -> ProjectRecord:
    return ProjectRecord(
        project_id="tier2-demo", name="tier2-demo", root_path=root_path,
        project_type="python_tool", stack=["python"],
        risk_profile="medium_high", advanced_math_score=0,
        test_commands=["pytest"],
    )


# ── wiring tests ──────────────────────────────────────────────────────


def test_semgrep_witness_runs_at_tier_2(tmp_path):
    """At tier 2 (smoke witness territory), semgrep should also run."""
    root = tmp_path / "demo"; root.mkdir()
    (root / "analysis.py").write_text("VALUE = 1\n", encoding="utf-8")

    engine = TruthCertEngine(tmp_path / "baselines")
    _force_preflight_ok(engine)
    _install_stubs(engine, semgrep_v="PASS")

    bundle = engine.verify(_tier2_project(str(root)))
    types = [w.witness_type for w in bundle.witness_results]
    assert "semgrep" in types, \
        f"semgrep witness should run at tier 2; bundle had {types}"


def test_semgrep_witness_skipped_at_tier_1(tmp_path):
    """At tier 1 (low-risk), only test_suite runs — semgrep should NOT
    run, since tier 1 is intentionally cheap."""
    root = tmp_path / "demo"; root.mkdir()
    (root / "analysis.py").write_text("VALUE = 1\n", encoding="utf-8")

    engine = TruthCertEngine(tmp_path / "baselines")
    _force_preflight_ok(engine)
    _install_stubs(engine)

    bundle = engine.verify(_tier1_project(str(root)))
    types = [w.witness_type for w in bundle.witness_results]
    assert "semgrep" not in types, \
        f"semgrep should NOT run at tier 1; bundle had {types}"


def test_all_pass_with_semgrep_yields_certified(tmp_path):
    """All-PASS including semgrep -> CERTIFIED (full release-grade)."""
    root = tmp_path / "demo"; root.mkdir()
    (root / "analysis.py").write_text("VALUE = 1\n", encoding="utf-8")

    engine = TruthCertEngine(tmp_path / "baselines")
    _force_preflight_ok(engine)
    _install_stubs(engine, test_v="PASS", smoke_v="PASS", semgrep_v="PASS")

    bundle = engine.verify(_tier2_project(str(root)))
    assert bundle.verdict == "CERTIFIED", \
        f"all-PASS should be CERTIFIED, got {bundle.verdict!r}"


def test_semgrep_fail_blocks_certified(tmp_path):
    """Semgrep FAIL with other witnesses PASS -> REJECT (witnesses disagree).
    A security finding must NOT pass through to CERTIFIED just because the
    test suite is green."""
    root = tmp_path / "demo"; root.mkdir()
    (root / "analysis.py").write_text("VALUE = 1\n", encoding="utf-8")

    engine = TruthCertEngine(tmp_path / "baselines")
    _force_preflight_ok(engine)
    _install_stubs(engine, test_v="PASS", smoke_v="PASS", semgrep_v="FAIL")

    bundle = engine.verify(_tier2_project(str(root)))
    assert bundle.verdict in {"FAIL", "REJECT"}, \
        f"semgrep FAIL must block CERTIFIED; got {bundle.verdict!r}"


def test_semgrep_skip_does_not_break_bundle(tmp_path):
    """Semgrep SKIP (e.g. binary not installed) must not break the bundle.
    Per the UNVERIFIED-vs-PASS lesson (2026-04-15), SKIP for missing
    optional input is graceful degradation; only NUMERICAL SKIP triggers
    UNVERIFIED. Semgrep SKIP should drop out of the non_skip set and
    leave the bundle CERTIFIED if everything else PASSes."""
    root = tmp_path / "demo"; root.mkdir()
    (root / "analysis.py").write_text("VALUE = 1\n", encoding="utf-8")

    engine = TruthCertEngine(tmp_path / "baselines")
    _force_preflight_ok(engine)
    _install_stubs(engine, test_v="PASS", smoke_v="PASS", semgrep_v="SKIP")

    bundle = engine.verify(_tier2_project(str(root)))
    assert bundle.verdict == "CERTIFIED", \
        f"semgrep SKIP should not block CERTIFIED when all else PASS; " \
        f"got {bundle.verdict!r} ({bundle.arbitration_reason!r})"


def test_engine_default_constructs_real_semgrep_witness(tmp_path):
    """Constructor should instantiate a real SemgrepWitness when no override
    is provided. Detected by attribute presence + type check."""
    from overmind.verification.semgrep_witness import SemgrepWitness
    engine = TruthCertEngine(tmp_path / "baselines")
    assert hasattr(engine, "semgrep_witness"), \
        "engine should expose semgrep_witness attribute"
    assert isinstance(engine.semgrep_witness, SemgrepWitness), \
        "default semgrep_witness should be SemgrepWitness instance"
