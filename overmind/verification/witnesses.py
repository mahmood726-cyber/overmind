"""Witness types for TruthCert multi-witness verification.

Current set: SuiteWitness, SmokeWitness, NumericalWitness,
DeterminismWitness, RegressionWitness. Determinism and Regression are
optional — added for projects whose release contract requires
reproducibility or no-regression guarantees.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

from overmind.subprocess_utils import split_command, validate_command_prefix_with_detail
from overmind.verification.policy_guard import PolicyGuard
from overmind.verification.scope_lock import WitnessResult

PYTHON_EXE = sys.executable


class SuiteWitness:
    def __init__(self, timeout: int = 120) -> None:
        self.timeout = timeout
        self.policy_guard = PolicyGuard()

    def run(self, command: str, cwd: str) -> WitnessResult:
        start = time.time()
        valid, detail = validate_command_prefix_with_detail(command, cwd=cwd)
        if not valid:
            return WitnessResult(
                witness_type="test_suite", verdict="FAIL", exit_code=-1,
                stdout="", stderr=detail or f"Blocked: command prefix not allowlisted: {command[:80]}",
                elapsed=round(time.time() - start, 2),
            )
        blocking_violation = next(
            (violation for violation in self.policy_guard.evaluate([command]) if violation.severity == "block"),
            None,
        )
        if blocking_violation is not None:
            return WitnessResult(
                witness_type="test_suite", verdict="FAIL", exit_code=-1,
                stdout="",
                stderr=(
                    f"Blocked: policy violation {blocking_violation.rule_name}: "
                    f"{blocking_violation.message}"
                ),
                elapsed=round(time.time() - start, 2),
            )
        try:
            proc = subprocess.run(
                split_command(command), cwd=cwd, shell=False,
                capture_output=True, text=True, timeout=self.timeout,
            )
            elapsed = time.time() - start
            verdict = "PASS" if proc.returncode == 0 else "FAIL"
            return WitnessResult(
                witness_type="test_suite", verdict=verdict,
                exit_code=proc.returncode,
                stdout=proc.stdout[-2000:], stderr=proc.stderr[-2000:],
                elapsed=round(elapsed, 2),
            )
        except subprocess.TimeoutExpired:
            return WitnessResult(
                witness_type="test_suite", verdict="FAIL", exit_code=-1,
                stdout="", stderr=f"Timed out after {self.timeout}s",
                elapsed=round(time.time() - start, 2),
            )
        except OSError as exc:
            return WitnessResult(
                witness_type="test_suite", verdict="FAIL", exit_code=-1,
                stdout="", stderr=f"Failed to start: {exc}",
                elapsed=round(time.time() - start, 2),
            )


class SmokeWitness:
    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout

    def run(self, modules: list[str], cwd: str) -> WitnessResult:
        if not modules:
            return WitnessResult(
                witness_type="smoke", verdict="SKIP", exit_code=None,
                stdout="", stderr="No modules to check", elapsed=0.0,
            )
        start = time.time()
        failures: list[str] = []
        env = os.environ.copy()
        # Ensure the project root itself is on PYTHONPATH so top-level sibling
        # modules (e.g. `shared.py` at repo root being imported from
        # `curate/extract_aact.py`) resolve. Also add src/ when present.
        pythonpath_parts = [str(Path(cwd))]
        src_dir = Path(cwd) / "src"
        if src_dir.is_dir():
            pythonpath_parts.insert(0, str(src_dir))
        existing = env.get("PYTHONPATH")
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts + ([existing] if existing else []))
        for module in modules:
            try:
                if module.startswith("js:"):
                    target_path = module.split(":", 1)[1]
                    proc = subprocess.run(
                        ["node", "--check", target_path],
                        cwd=cwd, capture_output=True, text=True,
                        timeout=self.timeout,
                    )
                else:
                    import_target = module.split(":", 1)[1] if module.startswith("py:") else module
                    proc = subprocess.run(
                        [PYTHON_EXE, "-c", f"import {import_target}"],
                        cwd=cwd, capture_output=True, text=True,
                        timeout=self.timeout, env=env,
                    )
                if proc.returncode != 0:
                    failures.append(f"{module}: {proc.stderr.strip()[-200:]}")
            except subprocess.TimeoutExpired:
                failures.append(f"{module}: import timed out")
            except OSError as exc:
                failures.append(f"{module}: {exc}")

        elapsed = round(time.time() - start, 2)
        if failures:
            return WitnessResult(
                witness_type="smoke", verdict="FAIL", exit_code=1,
                stdout="", stderr="\n".join(failures), elapsed=elapsed,
            )
        return WitnessResult(
            witness_type="smoke", verdict="PASS", exit_code=0,
            stdout=f"{len(modules)} modules imported OK",
            stderr="", elapsed=elapsed,
        )


class NumericalWitness:
    def __init__(
        self,
        timeout: int = 30,
        *,
        proposed_baselines_dir: str | Path | None = None,
    ) -> None:
        self.timeout = timeout
        self.policy_guard = PolicyGuard()
        # When set, a missing baseline triggers a PROBE run: we execute the
        # witness command once and write the captured numerics to
        # `<proposed_baselines_dir>/<project_id>.json` for human approval.
        # The proposed baseline is NEVER automatically promoted to
        # `data/baselines/` — user must move the file explicitly, so this
        # doesn't break the "memory != evidence" contract.
        self.proposed_baselines_dir = (
            Path(proposed_baselines_dir) if proposed_baselines_dir else None
        )

    def probe_and_propose(
        self,
        project_id: str,
        probe_command: str,
        cwd: str,
        expected_keys: list[str] | None = None,
        tolerance: float = 1e-6,
    ) -> WitnessResult:
        """Run a command once, capture JSON output, propose it as a baseline.

        Returns a SKIP verdict on success (since we didn't actually verify
        against a baseline) with details pointing to the proposed file. User
        reviews the JSON and moves it to `data/baselines/` to accept.
        """
        if self.proposed_baselines_dir is None:
            return WitnessResult(
                witness_type="numerical", verdict="SKIP", exit_code=None,
                stdout="", stderr="No proposed_baselines_dir configured; cannot probe.",
                elapsed=0.0,
            )
        start = time.time()
        valid, detail = validate_command_prefix_with_detail(probe_command, cwd=cwd)
        if not valid:
            return WitnessResult(
                witness_type="numerical", verdict="SKIP", exit_code=-1,
                stdout="", stderr=(detail or "probe command not allowlisted"),
                elapsed=round(time.time() - start, 2),
            )
        try:
            proc = subprocess.run(
                split_command(probe_command), cwd=cwd, shell=False,
                capture_output=True, text=True, timeout=self.timeout,
                encoding="utf-8", errors="replace",
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return WitnessResult(
                witness_type="numerical", verdict="SKIP", exit_code=-1,
                stdout="", stderr=f"Probe failed: {exc}",
                elapsed=round(time.time() - start, 2),
            )
        if proc.returncode != 0:
            return WitnessResult(
                witness_type="numerical", verdict="SKIP", exit_code=proc.returncode,
                stdout=proc.stdout[-500:], stderr=f"Probe exited {proc.returncode}: {proc.stderr[-300:]}",
                elapsed=round(time.time() - start, 2),
            )
        try:
            values = json.loads(proc.stdout.strip())
        except (json.JSONDecodeError, ValueError):
            return WitnessResult(
                witness_type="numerical", verdict="SKIP", exit_code=proc.returncode,
                stdout=proc.stdout[-500:], stderr="Probe output was not JSON; cannot propose baseline.",
                elapsed=round(time.time() - start, 2),
            )
        if expected_keys:
            values = {k: values[k] for k in expected_keys if k in values}
        if not values:
            return WitnessResult(
                witness_type="numerical", verdict="SKIP", exit_code=proc.returncode,
                stdout="", stderr="Probe produced an empty value set; nothing to propose.",
                elapsed=round(time.time() - start, 2),
            )
        self.proposed_baselines_dir.mkdir(parents=True, exist_ok=True)
        proposed_path = self.proposed_baselines_dir / f"{project_id}.json"
        proposed_payload = {
            "command": probe_command,
            "values": values,
            "tolerance": tolerance,
            "proposed": True,
            "proposed_at": _utc_now(),
            "note": (
                "Auto-proposed baseline from NumericalWitness.probe_and_propose. "
                "Review the values and move this file to data/baselines/<project_id>.json "
                "to accept."
            ),
        }
        proposed_path.write_text(
            json.dumps(proposed_payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return WitnessResult(
            witness_type="numerical", verdict="SKIP", exit_code=0,
            stdout=f"{len(values)} values probed",
            stderr=f"Proposed baseline written to {proposed_path}; review and promote to accept.",
            elapsed=round(time.time() - start, 2),
        )

    def run(self, baseline_path: str, cwd: str) -> WitnessResult:
        from pathlib import Path

        path = Path(baseline_path)
        if not path.exists():
            return WitnessResult(
                witness_type="numerical", verdict="SKIP", exit_code=None,
                stdout="", stderr=f"No baseline at {baseline_path}", elapsed=0.0,
            )

        start = time.time()
        baseline = json.loads(path.read_text(encoding="utf-8"))
        command = baseline["command"]
        expected = baseline["values"]
        tolerance = baseline.get("tolerance", 1e-6)

        valid, detail = validate_command_prefix_with_detail(command, cwd=cwd)
        if not valid:
            return WitnessResult(
                witness_type="numerical", verdict="FAIL", exit_code=-1,
                stdout="", stderr=detail or f"Blocked: command prefix not allowlisted: {command[:80]}",
                elapsed=round(time.time() - start, 2),
            )
        blocking_violation = next(
            (violation for violation in self.policy_guard.evaluate([command]) if violation.severity == "block"),
            None,
        )
        if blocking_violation is not None:
            return WitnessResult(
                witness_type="numerical", verdict="FAIL", exit_code=-1,
                stdout="",
                stderr=(
                    f"Blocked: policy violation {blocking_violation.rule_name}: "
                    f"{blocking_violation.message}"
                ),
                elapsed=round(time.time() - start, 2),
            )

        try:
            proc = subprocess.run(
                split_command(command), cwd=cwd, shell=False,
                capture_output=True, text=True, timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return WitnessResult(
                witness_type="numerical", verdict="FAIL", exit_code=-1,
                stdout="", stderr=f"Baseline command timed out after {self.timeout}s",
                elapsed=round(time.time() - start, 2),
            )
        except OSError as exc:
            return WitnessResult(
                witness_type="numerical", verdict="FAIL", exit_code=-1,
                stdout="", stderr=f"Failed to start: {exc}",
                elapsed=round(time.time() - start, 2),
            )

        if proc.returncode != 0:
            return WitnessResult(
                witness_type="numerical", verdict="FAIL",
                exit_code=proc.returncode,
                stdout=proc.stdout[-500:],
                stderr=f"Command failed: {proc.stderr.strip()[-500:]}",
                elapsed=round(time.time() - start, 2),
            )

        try:
            actual = json.loads(proc.stdout.strip())
        except (json.JSONDecodeError, ValueError):
            return WitnessResult(
                witness_type="numerical", verdict="FAIL", exit_code=0,
                stdout=proc.stdout[-500:],
                stderr="Could not parse output as JSON",
                elapsed=round(time.time() - start, 2),
            )

        drifts: list[str] = []
        for key, expected_val in expected.items():
            actual_val = actual.get(key)
            if actual_val is None:
                drifts.append(f"{key}: missing in output")
            elif isinstance(expected_val, (int, float)) and isinstance(actual_val, (int, float)):
                # Relative tolerance for large values, absolute for near-zero
                effective_tol = max(tolerance, tolerance * abs(expected_val))
                if abs(actual_val - expected_val) > effective_tol:
                    drifts.append(f"{key}: {expected_val} -> {actual_val} (delta={abs(actual_val - expected_val):.2e}, tol={effective_tol:.2e})")
            elif actual_val != expected_val:
                drifts.append(f"{key}: {expected_val!r} -> {actual_val!r}")

        elapsed = round(time.time() - start, 2)
        if drifts:
            return WitnessResult(
                witness_type="numerical", verdict="FAIL", exit_code=0,
                stdout=proc.stdout[-500:],
                stderr="Numerical drift: " + "; ".join(drifts),
                elapsed=elapsed,
            )
        return WitnessResult(
            witness_type="numerical", verdict="PASS", exit_code=0,
            stdout=f"{len(expected)} values within tolerance",
            stderr="", elapsed=elapsed,
        )


# Patterns stripped before comparing outputs for determinism — ISO dates,
# timestamps, elapsed times, and `in X.XXs` markers that pytest emits.
_NONDETERMINISTIC_PATTERNS = [
    (re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?"), "<TS>"),
    (re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:[.,]\d+)?"), "<TS>"),
    (re.compile(r"\d+\.\d+s\b"), "<DUR>"),
    (re.compile(r"\belapsed=\d+\.\d+"), "elapsed=<DUR>"),
    (re.compile(r"\bin \d+\.\d+ ?s"), "in <DUR>"),
    (re.compile(r"0x[0-9a-fA-F]+"), "<ADDR>"),
    (re.compile(r"/tmp/[\w./-]+"), "<TMP>"),
    (re.compile(r"\\AppData\\Local\\Temp\\[\w./\\-]+"), "<TMP>"),
]


def _normalize_for_determinism(text: str) -> str:
    """Strip common nondeterministic markers (timestamps, durations, addresses,
    temp-paths) so two runs of the same command can be hashed for equality."""
    import re as _re  # local alias because `re` is module-global
    normalized = text
    for pattern, replacement in _NONDETERMINISTIC_PATTERNS:
        normalized = pattern.sub(replacement, normalized)
    # Collapse trailing whitespace per line for CRLF/LF neutrality.
    normalized = "\n".join(line.rstrip() for line in normalized.splitlines())
    return normalized


class DeterminismWitness:
    """Run a command twice; PASS iff normalized outputs hash-match.

    Catches flaky tests, clock-dependent logic, and hidden nondeterminism
    that breaks numerical baselines across nightlies. Use for tier-3
    projects where reproducibility is a release requirement.
    """

    def __init__(self, timeout: int = 60) -> None:
        self.timeout = timeout
        self.policy_guard = PolicyGuard()

    def run(self, command: str, cwd: str) -> WitnessResult:
        import hashlib as _hashlib

        start = time.time()
        valid, detail = validate_command_prefix_with_detail(command, cwd=cwd)
        if not valid:
            return WitnessResult(
                witness_type="determinism", verdict="FAIL", exit_code=-1,
                stdout="", stderr=detail or f"Blocked: command prefix not allowlisted: {command[:80]}",
                elapsed=round(time.time() - start, 2),
            )
        blocking_violation = next(
            (v for v in self.policy_guard.evaluate([command]) if v.severity == "block"),
            None,
        )
        if blocking_violation is not None:
            return WitnessResult(
                witness_type="determinism", verdict="FAIL", exit_code=-1,
                stdout="",
                stderr=f"Blocked: policy violation {blocking_violation.rule_name}: {blocking_violation.message}",
                elapsed=round(time.time() - start, 2),
            )

        outputs: list[str] = []
        for run_idx in range(2):
            try:
                proc = subprocess.run(
                    split_command(command), cwd=cwd, shell=False,
                    capture_output=True, text=True, timeout=self.timeout,
                    encoding="utf-8", errors="replace",
                )
            except subprocess.TimeoutExpired:
                return WitnessResult(
                    witness_type="determinism", verdict="FAIL", exit_code=-1,
                    stdout="", stderr=f"Run {run_idx + 1} timed out after {self.timeout}s",
                    elapsed=round(time.time() - start, 2),
                )
            except OSError as exc:
                return WitnessResult(
                    witness_type="determinism", verdict="FAIL", exit_code=-1,
                    stdout="", stderr=f"Run {run_idx + 1} failed to start: {exc}",
                    elapsed=round(time.time() - start, 2),
                )
            if proc.returncode != 0:
                return WitnessResult(
                    witness_type="determinism", verdict="FAIL",
                    exit_code=proc.returncode,
                    stdout=proc.stdout[-500:],
                    stderr=f"Run {run_idx + 1} exited {proc.returncode}: {proc.stderr.strip()[-300:]}",
                    elapsed=round(time.time() - start, 2),
                )
            outputs.append(proc.stdout)

        normalized = [_normalize_for_determinism(o) for o in outputs]
        hashes = [_hashlib.sha256(n.encode("utf-8", errors="replace")).hexdigest()[:16] for n in normalized]
        elapsed = round(time.time() - start, 2)
        if hashes[0] == hashes[1]:
            return WitnessResult(
                witness_type="determinism", verdict="PASS", exit_code=0,
                stdout=f"Two runs produced identical normalized output ({hashes[0]})",
                stderr="", elapsed=elapsed,
            )
        # Emit a short first-diff line for operator triage.
        from difflib import unified_diff
        diff = list(unified_diff(
            normalized[0].splitlines()[:50],
            normalized[1].splitlines()[:50],
            lineterm="", n=1,
        ))
        return WitnessResult(
            witness_type="determinism", verdict="FAIL", exit_code=0,
            stdout=f"Hashes differ: {hashes[0]} vs {hashes[1]}",
            stderr="Nondeterministic output:\n" + "\n".join(diff[:20]),
            elapsed=elapsed,
        )


class RegressionWitness:
    """Git-aware: run tests against a prior commit, compare pass/fail counts.

    Fails the bundle if the current tree has MORE failures than the prior
    commit (i.e., the change introduced regressions). SKIPs when the project
    is not a git repository or when the prior ref can't be resolved. Does NOT
    modify the working tree — uses `git worktree add` instead of stash/checkout
    so concurrent work is unaffected.
    """

    # Rough pytest-style regexes. Good enough for PASS/FAIL counts; not a
    # substitute for the test runner's own machine-readable output.
    _SUMMARY_RE = re.compile(
        r"(?:=+\s*)?"
        r"(?:(\d+)\s+failed[^,\n]*)?[,\s]*"
        r"(?:(\d+)\s+passed[^,\n]*)?",
        re.IGNORECASE,
    )

    def __init__(self, timeout: int = 120) -> None:
        self.timeout = timeout
        self.policy_guard = PolicyGuard()

    def run(
        self,
        test_command: str,
        cwd: str,
        prior_ref: str = "HEAD~1",
    ) -> WitnessResult:
        start = time.time()
        valid, detail = validate_command_prefix_with_detail(test_command, cwd=cwd)
        if not valid:
            return WitnessResult(
                witness_type="regression", verdict="FAIL", exit_code=-1,
                stdout="", stderr=detail or "test command not allowlisted",
                elapsed=round(time.time() - start, 2),
            )
        cwd_path = Path(cwd)
        if not (cwd_path / ".git").exists():
            return WitnessResult(
                witness_type="regression", verdict="SKIP", exit_code=None,
                stdout="", stderr="Not a git repository; regression witness skipped.",
                elapsed=round(time.time() - start, 2),
            )
        # Verify the prior ref exists.
        try:
            verify = subprocess.run(
                ["git", "rev-parse", "--verify", prior_ref],
                cwd=cwd, capture_output=True, text=True, timeout=10,
                encoding="utf-8", errors="replace",
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return WitnessResult(
                witness_type="regression", verdict="SKIP", exit_code=None,
                stdout="", stderr=f"git rev-parse failed: {exc}",
                elapsed=round(time.time() - start, 2),
            )
        if verify.returncode != 0:
            return WitnessResult(
                witness_type="regression", verdict="SKIP", exit_code=None,
                stdout="", stderr=f"prior ref {prior_ref!r} not found",
                elapsed=round(time.time() - start, 2),
            )

        # Run on current tree first (cheap if already passing).
        current = self._run_tests(test_command, cwd)
        current_fails = self._count_failures(current.stdout + current.stderr)

        # Create a detached worktree at prior_ref so we don't touch the main tree.
        import tempfile
        worktree_dir = Path(tempfile.mkdtemp(prefix="overmind-regwitness-"))
        try:
            add = subprocess.run(
                ["git", "worktree", "add", "--detach", str(worktree_dir), prior_ref],
                cwd=cwd, capture_output=True, text=True, timeout=30,
                encoding="utf-8", errors="replace",
            )
            if add.returncode != 0:
                return WitnessResult(
                    witness_type="regression", verdict="SKIP", exit_code=None,
                    stdout="", stderr=f"git worktree add failed: {add.stderr.strip()[:300]}",
                    elapsed=round(time.time() - start, 2),
                )
            prior = self._run_tests(test_command, str(worktree_dir))
            prior_fails = self._count_failures(prior.stdout + prior.stderr)
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree_dir)],
                cwd=cwd, capture_output=True, text=True, timeout=15,
            )

        elapsed = round(time.time() - start, 2)
        if current_fails is None or prior_fails is None:
            return WitnessResult(
                witness_type="regression", verdict="SKIP", exit_code=None,
                stdout=f"current_fails={current_fails} prior_fails={prior_fails}",
                stderr="Could not parse pass/fail counts from test output.",
                elapsed=elapsed,
            )
        delta = current_fails - prior_fails
        if delta > 0:
            return WitnessResult(
                witness_type="regression", verdict="FAIL", exit_code=0,
                stdout=f"regressions: {delta} (current_fails={current_fails}, prior_fails={prior_fails})",
                stderr=f"Change introduced {delta} test regression(s) vs {prior_ref}.",
                elapsed=elapsed,
            )
        return WitnessResult(
            witness_type="regression", verdict="PASS", exit_code=0,
            stdout=f"no regression (current_fails={current_fails}, prior_fails={prior_fails})",
            stderr="", elapsed=elapsed,
        )

    def _run_tests(self, command: str, cwd: str) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                split_command(command), cwd=cwd, shell=False,
                capture_output=True, text=True, timeout=self.timeout,
                encoding="utf-8", errors="replace",
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return subprocess.CompletedProcess(
                args=command, returncode=-1, stdout="",
                stderr=f"test run failed: {exc}",
            )

    @classmethod
    def _count_failures(cls, output: str) -> int | None:
        """Parse pytest-style summary. Returns None when unparseable."""
        # Look at the last ~200 lines for a summary.
        tail = "\n".join(output.splitlines()[-50:])
        # Explicit pytest summary forms.
        failed_match = re.search(r"(\d+)\s+failed", tail, re.IGNORECASE)
        passed_match = re.search(r"(\d+)\s+passed", tail, re.IGNORECASE)
        if failed_match is not None:
            return int(failed_match.group(1))
        if passed_match is not None:
            return 0  # N passed, 0 failed implicit
        return None
