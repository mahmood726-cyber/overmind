"""pip-audit as an Overmind witness — Python dep CVE coverage.

Why this witness exists:
  Sentinel pre-push catches code-level past-incident bugs.
  SemgrepWitness covers code-level OWASP / shell-injection / secret leaks.
  NumericalWitness covers estimator drift.
  None of those check "your installed `requests==2.25.0` has CVE-2024-12345
  fixed in 2.31.6" — that's a different scanner. PipAuditWitness wires
  pip-audit (PyPA-maintained, queries the PyPI Advisory Database) as
  one more nightly check.

Verdict mapping (mirrors SemgrepWitness for consistency):
  Any vulnerability found              -> FAIL
  No vulnerabilities                   -> PASS
  pip-audit not on PATH                -> SKIP (graceful degradation)
  subprocess timeout/crash             -> FAIL with explicit reason
  unparseable JSON                     -> FAIL (don't silently treat
                                         garbage as PASS)

Default invocation:
  pip-audit --format=json --strict --requirement=<best-found-reqs-file>
  ... or, if no requirements file present:
  pip-audit --format=json --strict
  (audits the current installed env)

The `--strict` flag makes pip-audit treat skipped dependencies (e.g.,
deps it couldn't resolve) as errors rather than silent passes — the
same fail-closed posture as the rest of Overmind.

Spec: https://github.com/pypa/pip-audit
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Sequence

from overmind.verification.scope_lock import WitnessResult

DEFAULT_TIMEOUT_S = 180

# Files we look for IN the repo, in priority order. First-found wins.
# If none present, we fall back to scanning the active env.
DEFAULT_REQUIREMENTS_CANDIDATES: tuple[str, ...] = (
    "requirements.txt",
    "requirements/base.txt",
    "requirements/prod.txt",
    "requirements/main.txt",
)


class PipAuditWitness:
    """Run pip-audit against a repo. PASS unless any CVE found."""

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT_S,
        binary: str = "pip-audit",
        requirements_candidates: Sequence[str] | None = None,
        scan_active_env_when_no_requirements: bool = False,
    ) -> None:
        self.timeout = timeout
        self.binary = binary
        self.requirements_candidates = (
            tuple(requirements_candidates)
            if requirements_candidates is not None
            else DEFAULT_REQUIREMENTS_CANDIDATES
        )
        # Default False (changed 2026-04-29 after canary regression):
        # auditing the active env when a repo declares no requirements is
        # rarely what callers want — it conflates the host system's CVEs
        # with the repo under test, breaking the meta-verification canary
        # and any minimal-fixture project. Opt in explicitly if needed.
        self.scan_active_env_when_no_requirements = scan_active_env_when_no_requirements

    def _find_requirements(self, cwd: str) -> str | None:
        repo = Path(cwd)
        for rel in self.requirements_candidates:
            f = repo / rel
            if f.is_file():
                return rel
        return None

    def _build_cmd(self, requirements: str | None) -> list[str]:
        cmd = [self.binary, "--format=json", "--strict"]
        if requirements is not None:
            cmd.extend(["--requirement", requirements])
        # When requirements is None, pip-audit audits the active env.
        return cmd

    def run(self, cwd: str) -> WitnessResult:
        start = time.time()
        requirements = self._find_requirements(cwd)
        if requirements is None and not self.scan_active_env_when_no_requirements:
            # No requirements file → SKIP (changed 2026-04-29). Active-env
            # scanning conflates host CVEs with the repo under test and
            # produces noise on minimal-fixture projects (canary, smoke
            # tests). Opt in via scan_active_env_when_no_requirements=True.
            return WitnessResult(
                witness_type="pip_audit",
                verdict="SKIP",
                exit_code=0,
                stdout="",
                stderr=(
                    "no requirements.txt / pyproject.toml / requirements/ "
                    "subtree found at repo root — SKIP. Opt in via "
                    "scan_active_env_when_no_requirements=True if you "
                    "want to audit the host environment anyway."
                ),
                elapsed=round(time.time() - start, 2),
            )
        cmd = self._build_cmd(requirements)
        try:
            proc = subprocess.run(
                cmd, cwd=cwd, capture_output=True, text=True,
                timeout=self.timeout, encoding="utf-8", errors="replace",
            )
        except FileNotFoundError:
            return WitnessResult(
                witness_type="pip_audit",
                verdict="SKIP",
                exit_code=-1,
                stdout="",
                stderr=(
                    f"pip-audit binary not found (searched: {self.binary!r}). "
                    "Install via `pip install pip-audit` or set the binary "
                    "argument; this run is SKIP, not FAIL."
                ),
                elapsed=round(time.time() - start, 2),
            )
        except subprocess.TimeoutExpired:
            return WitnessResult(
                witness_type="pip_audit",
                verdict="FAIL",
                exit_code=-1,
                stdout="",
                stderr=f"pip-audit timed out after {self.timeout}s",
                elapsed=round(time.time() - start, 2),
            )

        elapsed = round(time.time() - start, 2)

        # Parse JSON. Garbage stdout → FAIL (never silently treat as PASS).
        try:
            payload = json.loads(proc.stdout) if proc.stdout else {}
        except json.JSONDecodeError as exc:
            return WitnessResult(
                witness_type="pip_audit",
                verdict="FAIL",
                exit_code=proc.returncode,
                stdout=proc.stdout[-2000:],
                stderr=(
                    f"pip-audit produced unparseable JSON: {exc.msg}. "
                    f"stderr tail: {proc.stderr[-500:]}"
                ),
                elapsed=elapsed,
            )

        deps = payload.get("dependencies", []) if isinstance(payload, dict) else []

        # Count vulns. Each dep entry has a "vulns" list (empty for clean).
        vuln_records: list[tuple[str, str, str]] = []
        # (package_name, version, vuln_id)
        for d in deps:
            if not isinstance(d, dict):
                continue
            pkg = d.get("name") or "?"
            ver = d.get("version") or "?"
            for v in d.get("vulns") or []:
                if not isinstance(v, dict):
                    continue
                vid = v.get("id") or (v.get("aliases") or [""])[0] or "?"
                vuln_records.append((pkg, ver, vid))

        n_vulns = len(vuln_records)
        verdict = "FAIL" if n_vulns > 0 else "PASS"

        # Compose grep-friendly summary.
        scope = (
            f"requirements file: {requirements}"
            if requirements is not None
            else "active env (no requirements file found)"
        )
        summary_lines: list[str] = [
            f"pip-audit findings: {n_vulns} vulnerabilit{'y' if n_vulns == 1 else 'ies'} "
            f"across {len(deps)} dep(s); scope: {scope}",
        ]
        if n_vulns > 0:
            summary_lines.append("vulnerable packages:")
            for pkg, ver, vid in vuln_records[:20]:
                summary_lines.append(f"  - {pkg} {ver}  {vid}")
            if n_vulns > 20:
                summary_lines.append(f"  ... and {n_vulns - 20} more")
            summary_lines.append(
                "fix: review pip-audit output, bump affected versions, "
                "rerun. If the fix is a major version bump that breaks "
                "your code, document the workaround in a SECURITY.md."
            )
        summary = "\n".join(summary_lines)

        # Match SuiteWitness convention: detail in stderr for FAIL,
        # stdout for PASS.
        return WitnessResult(
            witness_type="pip_audit",
            verdict=verdict,
            exit_code=proc.returncode,
            stdout=summary if verdict == "PASS" else proc.stdout[-1500:],
            stderr=summary if verdict == "FAIL" else (
                proc.stderr[-500:] if proc.stderr else summary
            ),
            elapsed=elapsed,
        )
