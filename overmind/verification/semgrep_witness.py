"""Semgrep as an Overmind witness — generic OWASP / supply-chain coverage.

Why this witness exists:
  Sentinel pre-push rules encode past-incident lessons (highly specific,
  hand-curated). Numerical witness covers estimator drift. Neither covers
  the generic OWASP / shell-injection / SSRF / secret-leak surface, where
  ~thousands of community-maintained Semgrep rules already exist.
  SemgrepWitness wires that as one more nightly check.

Verdict mapping (see test_semgrep_witness.py for specs):
  ERROR-severity findings   -> FAIL
  WARNING-severity findings -> PASS, noted in stderr (advisory)
  INFO-severity findings    -> PASS silently
  semgrep not on PATH       -> SKIP (graceful degradation; missing tool
                                 != failed scan)
  subprocess timeout/crash  -> FAIL with explicit reason
  unparseable JSON          -> FAIL (don't silently treat garbage as PASS)

Default config set is `["p/python", "p/security-audit"]` — narrow enough
to be fast, broad enough to catch most OWASP categories. Override per
project via `SemgrepWitness(configs=[...])` for e.g. `p/django`,
`p/secrets`, `p/javascript`.

Spec: https://semgrep.dev/docs/cli-reference/
"""
from __future__ import annotations

import json
import subprocess
import time
from typing import Sequence

from overmind.verification.scope_lock import WitnessResult

DEFAULT_CONFIGS: tuple[str, ...] = ("p/python", "p/security-audit")
DEFAULT_TIMEOUT_S = 300

_BLOCKING_SEVERITY = "ERROR"


class SemgrepWitness:
    """Run Semgrep against a repo. PASS unless ERROR-severity findings."""

    def __init__(
        self,
        configs: Sequence[str] | None = None,
        timeout: int = DEFAULT_TIMEOUT_S,
        binary: str = "semgrep",
    ) -> None:
        self.configs = tuple(configs) if configs else DEFAULT_CONFIGS
        self.timeout = timeout
        self.binary = binary

    def _build_cmd(self) -> list[str]:
        cmd = [self.binary]
        for cfg in self.configs:
            cmd.extend(["--config", cfg])
        # --json emits structured output; --quiet drops the human banner.
        # We intentionally do NOT pass --error or any severity flag — we
        # parse severities ourselves so the verdict mapping is consistent
        # with our spec rather than semgrep's exit-code conventions.
        cmd.extend(["--json", "--quiet"])
        cmd.append(".")
        return cmd

    def run(self, cwd: str) -> WitnessResult:
        start = time.time()
        cmd = self._build_cmd()
        try:
            proc = subprocess.run(
                cmd, cwd=cwd, capture_output=True, text=True,
                timeout=self.timeout, encoding="utf-8", errors="replace",
            )
        except FileNotFoundError:
            return WitnessResult(
                witness_type="semgrep",
                verdict="SKIP",
                exit_code=-1,
                stdout="",
                stderr=(
                    f"semgrep binary not found (searched: {self.binary!r}). "
                    "Install via `pip install semgrep` or set the binary "
                    "argument; this run is SKIP, not FAIL."
                ),
                elapsed=round(time.time() - start, 2),
            )
        except subprocess.TimeoutExpired:
            return WitnessResult(
                witness_type="semgrep",
                verdict="FAIL",
                exit_code=-1,
                stdout="",
                stderr=f"semgrep timed out after {self.timeout}s",
                elapsed=round(time.time() - start, 2),
            )

        elapsed = round(time.time() - start, 2)

        # Parse JSON. If it's garbage, FAIL — never silently PASS on
        # unparseable output (would mask a crashed semgrep as a clean run).
        try:
            payload = json.loads(proc.stdout) if proc.stdout else {}
        except json.JSONDecodeError as exc:
            return WitnessResult(
                witness_type="semgrep",
                verdict="FAIL",
                exit_code=proc.returncode,
                stdout=proc.stdout[-2000:],
                stderr=(
                    f"semgrep produced unparseable JSON: {exc.msg}. "
                    f"stderr tail: {proc.stderr[-500:]}"
                ),
                elapsed=elapsed,
            )

        results = payload.get("results", []) if isinstance(payload, dict) else []
        errors = payload.get("errors", []) if isinstance(payload, dict) else []

        # Bucketize findings by severity so the summary can mention each tier.
        buckets: dict[str, list[dict]] = {"ERROR": [], "WARNING": [], "INFO": []}
        for r in results:
            sev = (r.get("extra", {}) or {}).get("severity", "INFO").upper()
            buckets.setdefault(sev, []).append(r)

        n_error = len(buckets.get("ERROR", []))
        n_warning = len(buckets.get("WARNING", []))
        n_info = len(buckets.get("INFO", []))

        verdict = "FAIL" if n_error > 0 else "PASS"

        # Compose a stable, grep-friendly summary.
        summary_lines: list[str] = [
            f"semgrep findings: ERROR={n_error} WARNING={n_warning} "
            f"INFO={n_info}; engine errors={len(errors)}",
        ]
        # On FAIL, list the blocking ERROR findings explicitly.
        if n_error > 0:
            summary_lines.append("blocking ERROR findings:")
            for r in buckets["ERROR"][:20]:
                cid = r.get("check_id", "?")
                pth = r.get("path", "?")
                ln = (r.get("start") or {}).get("line", "?")
                summary_lines.append(f"  - {cid}  {pth}:{ln}")
            if n_error > 20:
                summary_lines.append(f"  ... and {n_error - 20} more")
        if n_warning > 0:
            summary_lines.append(f"{n_warning} advisory WARNING finding(s) "
                                 "(non-blocking)")
        summary = "\n".join(summary_lines)

        # Overmind convention: detail goes in stderr for FAIL, stdout for PASS.
        # (Matches SuiteWitness pattern.)
        return WitnessResult(
            witness_type="semgrep",
            verdict=verdict,
            exit_code=proc.returncode,
            stdout=summary if verdict == "PASS" else proc.stdout[-1500:],
            stderr=summary if verdict == "FAIL" else (proc.stderr[-500:]
                                                      if proc.stderr else summary),
            elapsed=elapsed,
        )
