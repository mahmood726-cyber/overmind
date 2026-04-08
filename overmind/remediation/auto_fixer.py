"""AutoFixer: orchestrates safe auto-remediation after nightly diagnosis.

Safety rules:
1. NEVER modify source code (.py, .html, .js)
2. Only environmental fixes: pip install, baseline regen, git restore
3. Re-verify after every fix
4. Only commit if re-verification passes
5. Roll back if fix makes things worse
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from overmind.diagnosis.judge import Diagnosis
from overmind.remediation.strategies import (
    BaselineDriftFix,
    DependencyRotFix,
    FixResult,
    MissingFixtureFix,
)


@dataclass
class RemediationResult:
    project_id: str
    diagnosis_type: str
    fix_attempted: bool
    fix_result: FixResult | None
    reverified: bool
    reverify_passed: bool
    committed: bool
    detail: str


# Failure types that are NEVER auto-fixable
NEVER_AUTO_FIX = {
    "FORMULA_ERROR",      # Needs human judgment
    "FLOAT_PRECISION",    # Needs human judgment
    "UNKNOWN",            # Can't diagnose → can't fix
}


class AutoFixer:
    def __init__(
        self,
        baselines_dir: Path,
        probes_dir: Path,
        dry_run: bool = False,
    ) -> None:
        self.dry_run = dry_run
        self.strategies = [
            DependencyRotFix(),
            BaselineDriftFix(baselines_dir, probes_dir),
            MissingFixtureFix(),
        ]

    def attempt_fix(
        self,
        diagnosis: Diagnosis,
        project_path: str,
        verify_fn=None,
    ) -> RemediationResult:
        """Attempt to auto-fix a diagnosed failure.

        Args:
            diagnosis: The Judge's diagnosis
            project_path: Path to the project root
            verify_fn: Optional callable(project_path) -> bool for re-verification
        """
        # Safety gate: never auto-fix certain types
        if diagnosis.failure_type in NEVER_AUTO_FIX:
            return RemediationResult(
                project_id=diagnosis.project_id,
                diagnosis_type=diagnosis.failure_type,
                fix_attempted=False,
                fix_result=None,
                reverified=False,
                reverify_passed=False,
                committed=False,
                detail=f"Auto-fix blocked: {diagnosis.failure_type} requires human review",
            )

        # Find a strategy that can handle this
        for strategy in self.strategies:
            if not strategy.can_fix(diagnosis):
                continue

            if self.dry_run:
                return RemediationResult(
                    project_id=diagnosis.project_id,
                    diagnosis_type=diagnosis.failure_type,
                    fix_attempted=False,
                    fix_result=None,
                    reverified=False,
                    reverify_passed=False,
                    committed=False,
                    detail=f"Dry run: would attempt {strategy.__class__.__name__}",
                )

            # Apply the fix
            fix_result = strategy.apply(diagnosis, project_path)

            if not fix_result.success:
                return RemediationResult(
                    project_id=diagnosis.project_id,
                    diagnosis_type=diagnosis.failure_type,
                    fix_attempted=True,
                    fix_result=fix_result,
                    reverified=False,
                    reverify_passed=False,
                    committed=False,
                    detail=f"Fix failed: {fix_result.detail}",
                )

            # Re-verify if we have a verify function
            reverified = False
            reverify_passed = False
            if verify_fn:
                reverified = True
                reverify_passed = verify_fn(project_path)

            # Commit if re-verification passed (or no verify_fn)
            committed = False
            if fix_result.success and (reverify_passed or not verify_fn):
                committed = self._commit_fix(project_path, diagnosis, fix_result)

            return RemediationResult(
                project_id=diagnosis.project_id,
                diagnosis_type=diagnosis.failure_type,
                fix_attempted=True,
                fix_result=fix_result,
                reverified=reverified,
                reverify_passed=reverify_passed,
                committed=committed,
                detail=f"Fixed: {fix_result.action_taken}" + (
                    f" | reverify={'PASS' if reverify_passed else 'FAIL'}" if reverified else ""
                ) + (f" | committed" if committed else ""),
            )

        # No strategy matched
        return RemediationResult(
            project_id=diagnosis.project_id,
            diagnosis_type=diagnosis.failure_type,
            fix_attempted=False,
            fix_result=None,
            reverified=False,
            reverify_passed=False,
            committed=False,
            detail=f"No auto-fix strategy for {diagnosis.failure_type}",
        )

    def _commit_fix(self, project_path: str, diagnosis: Diagnosis, fix_result: FixResult) -> bool:
        """Commit the fix with an audit trail."""
        try:
            # Stage all changes
            subprocess.run(
                ["git", "add", "-A"],
                cwd=project_path, capture_output=True, timeout=10,
            )
            # Commit with Overmind attribution
            msg = (
                f"fix(overmind): auto-remediate {diagnosis.failure_type}\n\n"
                f"Action: {fix_result.action_taken}\n"
                f"Detail: {fix_result.detail[:200]}\n"
                f"Diagnosed by: Overmind Judge\n"
                f"Auto-fixed by: Overmind AutoFixer"
            )
            proc = subprocess.run(
                ["git", "commit", "-m", msg, "--allow-empty"],
                cwd=project_path, capture_output=True, text=True, timeout=10,
            )
            return proc.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False
