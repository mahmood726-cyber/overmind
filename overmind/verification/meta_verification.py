"""Meta-verification canary: verify that the verifier itself is not broken.

Runs TruthCertEngine.verify() against a known-good fixture project whose
expected verdict is CERTIFIED. If the verifier reports anything other than
CERTIFIED for the canary, the verification layer itself is suspect and all
verdicts from the current nightly should be treated with skepticism.

Designed to be called at the start of every nightly before the main
verification sweep, and manually via `overmind meta-verify` for debugging.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from overmind.storage.models import ProjectRecord
from overmind.verification.truthcert_engine import TruthCertEngine


CANARY_PROJECT_ID = "overmind-canary"
CANARY_MODULE = "canary_module"
CANARY_TEST_FILE = "test_canary.py"


@dataclass(slots=True)
class MetaVerificationResult:
    passed: bool
    verdict: str
    failure_class: str | None
    reason: str
    bundle_hash: str


def build_canary_project(root: Path) -> ProjectRecord:
    """Create a minimal known-good fixture project on disk."""
    root.mkdir(parents=True, exist_ok=True)

    pkg = root / CANARY_MODULE
    pkg.mkdir(exist_ok=True)
    (pkg / "__init__.py").write_text(
        'VALUE = 42\n\ndef identity(x):\n    return x\n',
        encoding="utf-8",
    )

    tests_dir = root / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / CANARY_TEST_FILE).write_text(
        "from canary_module import VALUE, identity\n\n"
        "def test_value_is_42():\n"
        "    assert VALUE == 42\n\n"
        "def test_identity():\n"
        "    assert identity(7) == 7\n",
        encoding="utf-8",
    )

    import sys
    test_command = f'"{sys.executable}" -m pytest tests -q'
    return ProjectRecord(
        project_id=CANARY_PROJECT_ID,
        name="Overmind Canary",
        root_path=str(root),
        project_type="python_tool",
        stack=["python"],
        test_commands=[test_command],
        risk_profile="medium_high",  # tier 2 → test + smoke, no baseline required
        advanced_math_score=0,
    )


def run_meta_verification(
    canary_root: Path,
    baselines_dir: Path,
    *,
    test_timeout: int = 30,
) -> MetaVerificationResult:
    """Run TruthCertEngine against the canary project and assert CERTIFIED."""
    project = build_canary_project(canary_root)
    engine = TruthCertEngine(baselines_dir=baselines_dir, test_timeout=test_timeout)
    bundle = engine.verify(project)
    passed = bundle.verdict == "CERTIFIED"
    return MetaVerificationResult(
        passed=passed,
        verdict=bundle.verdict,
        failure_class=bundle.failure_class,
        reason=bundle.arbitration_reason,
        bundle_hash=bundle.bundle_hash,
    )


def write_meta_verification_alarm(data_dir: Path, result: MetaVerificationResult) -> Path:
    """Write a tracked alarm file when the canary fails.

    Nightly callers should treat the existence of this file (or a non-match
    between today's and yesterday's result) as a hard stop condition for
    promoting any verdict downstream.
    """
    alarm_path = data_dir / "meta_verification_alarm.json"
    alarm_path.parent.mkdir(parents=True, exist_ok=True)
    alarm_path.write_text(
        json.dumps(
            {
                "passed": result.passed,
                "verdict": result.verdict,
                "failure_class": result.failure_class,
                "reason": result.reason,
                "bundle_hash": result.bundle_hash,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return alarm_path
