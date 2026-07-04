"""Deterministic objective witnesses (the D2 floor under Arm C).

These compute ground-truth defects from the structured task ``data`` — NOT from a
model's opinion, and **without knowing the task kind** (the kind is part of the
answer; a real floor never sees it). ``run_witness`` runs the whole battery
blindly on the data and flags if ANY check fires:

  * impossible 2x2 cell (events > N),
  * an invalid confidence interval (lo>hi, or the point estimate outside it),
  * a pooled estimate that does not reproduce the raw studies (vs metafor).

Reviewer-only defect kinds are constructed so the data passes EVERY check (valid
counts, valid CI, claimed value matches the stated measure) — the defect lives
only in the narrative text, so the deterministic floor genuinely cannot catch it.
That is what forces the cross-vendor panel to earn its keep.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class WitnessResult:
    defect: bool
    detail: str = ""
    computed_value: float | None = None


def impossible_cell_witness(data: dict) -> WitnessResult:
    """Flag a 2x2 study where events exceed the arm total (events > N)."""
    for study in data.get("studies", []):
        ai, n1 = study.get("ai"), study.get("n1")
        ci, n2 = study.get("ci"), study.get("n2")
        if ai is not None and n1 is not None and ai > n1:
            return WitnessResult(True, f"{study.get('label','?')}: events {ai} > N {n1}")
        if ci is not None and n2 is not None and ci > n2:
            return WitnessResult(True, f"{study.get('label','?')}: control events {ci} > N {n2}")
    return WitnessResult(False)


def ci_witness(data: dict) -> WitnessResult:
    """Flag a claimed CI that is invalid: lo>hi, or the point estimate outside it."""
    ci = data.get("claimed_ci")
    val = data.get("claimed_value")
    if not ci or len(ci) != 2:
        return WitnessResult(False)
    lo, hi = float(ci[0]), float(ci[1])
    if lo > hi:
        return WitnessResult(True, f"CI lower {lo} > upper {hi} (transposed)")
    if val is not None and not (lo <= float(val) <= hi):
        return WitnessResult(True, f"point {val} outside CI [{lo}, {hi}]")
    return WitnessResult(False)


def reproduction_witness(data: dict, *, tol: float | None = None) -> WitnessResult:
    """Reproduce the pooled estimate from the raw studies and compare to the
    ``claimed_value`` in the artifact. A mismatch beyond tolerance is a defect."""
    from overmind.evidence.pooling import Study, pool

    claimed = data.get("claimed_value")
    if claimed is None or not data.get("studies"):
        return WitnessResult(False, "no claimed value/studies to check")
    tol = tol if tol is not None else data.get("tolerance", 0.05)
    try:
        measure = data.get("measure", "RR")
        studies = [Study(**s) for s in data["studies"]]
        result = pool(studies, measure=measure, method=data.get("method", "REML"))
        computed = result["estimate_ratio"] if result.get("estimate_ratio") is not None else result["estimate_log"]
    except Exception as exc:  # noqa: BLE001 — a pooling error is itself a defect signal
        return WitnessResult(True, f"pooling failed: {type(exc).__name__}", None)
    deviation = abs(computed - float(claimed))
    if deviation > tol:
        return WitnessResult(True, f"claimed {claimed} vs computed {computed:.5f} (dev {deviation:.5f} > tol {tol})", computed)
    return WitnessResult(False, f"claimed {claimed} ~ computed {computed:.5f}", computed)


# The battery, in order. Each takes ``data`` and returns a WitnessResult.
_BATTERY = (impossible_cell_witness, ci_witness, reproduction_witness)


def run_witness(task, *, tol: float | None = None) -> WitnessResult:
    """Run the FULL deterministic battery blindly on ``task.data`` (kind-agnostic).
    Flags if any check fires — this is Arm C's objective-gate floor."""
    data = getattr(task, "data", task if isinstance(task, dict) else {}) or {}
    for check in _BATTERY:
        if check is reproduction_witness:
            res = check(data, tol=tol)
        else:
            res = check(data)
        if res.defect:
            return res
    return WitnessResult(False)
