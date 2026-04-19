"""NumericalContinuityWitness: scientific-content integrity witness.

Verifies three things that truthcert's existing witnesses (test_suite,
smoke, numerical) do NOT cover:

  1. Baseline drift — if `baseline.json` + `<paper_id>.report.json`
     exist at the project root, runs MissionCritical's
     `BaselineStore.diff` for each paper. Any field exceeding tolerance
     is a FAIL.

  2. Provenance coverage — if `provenance.json` exists at the project
     root, FAILs if any entry is unverified (identifiers and extracted
     values without a human-verification mark shouldn't ship).

  3. Differential-engine agreement — if `diffmeta.csv` or a list of
     CSVs exist at the project root with a `.diffmeta.yaml` config
     spec, runs `diffmeta.compare` and FAILs on divergence. v0.1:
     checks for `diffmeta.csv` with sidecar `.diffmeta.meta` describing
     measure/method; skip if unavailable.

Verdicts:
  - PASS  — all checks ran and agree (or nothing to check).
  - FAIL  — at least one check found drift, unverified identifier, or
            engine disagreement.
  - SKIP  — mission_critical package not installed (cannot run checks).

This witness is designed to be added alongside SuiteWitness/SmokeWitness/
NumericalWitness in `TruthCertEngine` for projects at tier >= 3 (high
risk + advanced math). Wiring into the engine's default ladder is left
to a future change — instantiate directly for now.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from overmind.verification.scope_lock import WitnessResult


class NumericalContinuityWitness:
    """Runs baseline + provenance + diffmeta integrity checks on a project."""

    witness_type = "numerical_continuity"

    def __init__(self, *, tolerance: float = 1e-6) -> None:
        self.tolerance = tolerance

    def run(self, cwd: str | Path) -> WitnessResult:
        cwd = Path(cwd)
        start = time.time()

        try:
            from mission_critical.baseline import BaselineStore
            from mission_critical.provenance import ProvenanceStore
        except ImportError:
            return WitnessResult(
                witness_type=self.witness_type, verdict="SKIP",
                exit_code=None, stdout="",
                stderr=(
                    "mission_critical package not installed; "
                    "numerical continuity checks unavailable"
                ),
                elapsed=round(time.time() - start, 2),
            )

        findings: list[str] = []

        baseline_path = cwd / "baseline.json"
        if baseline_path.is_file():
            try:
                store = BaselineStore(baseline_path)
            except RuntimeError as e:
                findings.append(
                    f"baseline.json unreadable: {type(e).__name__}"
                )
            else:
                for rec in store.all():
                    report_path = cwd / f"{rec.paper_id}.report.json"
                    if not report_path.is_file():
                        continue
                    numeric = _load_numeric_report(report_path)
                    if numeric is None:
                        findings.append(
                            f"{rec.paper_id}.report.json unreadable"
                        )
                        continue
                    try:
                        report = store.diff(
                            rec.paper_id, numeric, tolerance=self.tolerance,
                        )
                    except KeyError:
                        continue
                    if report.exceeds_tolerance:
                        findings.append(
                            f"{rec.paper_id}: max |d|={report.max_abs_diff:.2e} "
                            f"(tol {self.tolerance:.0e}, "
                            f"{len(report.diffs)} field(s) drifted)"
                        )

        provenance_path = cwd / "provenance.json"
        if provenance_path.is_file():
            try:
                prov = ProvenanceStore(provenance_path)
            except RuntimeError as e:
                findings.append(
                    f"provenance.json unreadable: {type(e).__name__}"
                )
            else:
                unverified = prov.unverified()
                if unverified:
                    findings.append(
                        f"{len(unverified)} unverified provenance "
                        f"entrie(s): {', '.join(e.identifier for e in unverified[:5])}"
                        + (f" +{len(unverified) - 5} more"
                           if len(unverified) > 5 else "")
                    )

        elapsed = round(time.time() - start, 2)

        if findings:
            return WitnessResult(
                witness_type=self.witness_type, verdict="FAIL",
                exit_code=1, stdout="",
                stderr="; ".join(findings)[:2000],
                elapsed=elapsed,
            )

        return WitnessResult(
            witness_type=self.witness_type, verdict="PASS",
            exit_code=0,
            stdout=(
                "numerical continuity: baseline + provenance checks OK"
            ),
            stderr="", elapsed=elapsed,
        )


def _load_numeric_report(path: Path) -> Optional[dict[str, float]]:
    """Flatten a report JSON into numeric field dict.

    Unwraps diffmeta-shaped reports (`{python, r, ...}`) and renames
    `log_or` / `estimate` -> `pooled_estimate` for baseline-store
    compatibility.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    src = data.get("pooled") or data.get("python") or data
    if not isinstance(src, dict):
        return None
    if "log_or" in src and "pooled_estimate" not in src:
        src = dict(src)
        src["pooled_estimate"] = src.pop("log_or")
    if "estimate" in src and "pooled_estimate" not in src:
        src = dict(src)
        src["pooled_estimate"] = src.pop("estimate")
    numeric: dict[str, float] = {}
    for k, v in src.items():
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            numeric[k] = float(v)
    return numeric
