"""Deterministic objective witnesses (the D2 floor under Arm C).

These compute ground-truth defects from the structured task ``data`` — NOT from a
model's opinion. They are what Arm C runs beneath any "accept": an impossible 2x2
cell and a pooled-estimate reproduction. Reviewer-only defect kinds (DIRECTION)
are deliberately NOT witness-detectable, so the benchmark also measures the panel
where no deterministic gate exists.
"""
from __future__ import annotations

from dataclasses import dataclass

from overmind.benchmark.tasks import Task, DIRECTION, IMPOSSIBLE_CELL, REPRODUCTION


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


def reproduction_witness(data: dict, *, tol: float | None = None) -> WitnessResult:
    """Reproduce the pooled estimate from the raw studies and compare to the
    ``claimed_value`` in the artifact. A mismatch beyond tolerance is a defect."""
    from overmind.evidence.pooling import Study, pool

    claimed = data.get("claimed_value")
    if claimed is None:
        return WitnessResult(False, "no claimed value to check")
    tol = tol if tol is not None else data.get("tolerance", 0.01)
    try:
        measure = data.get("measure", "RR")
        studies = [Study(**s) for s in data["studies"]]
        result = pool(studies, measure=measure, method=data.get("method", "REML"))
        # ratio measures report on the natural (back-transformed) scale; difference
        # measures are already natural-scale in estimate_log.
        computed = result["estimate_ratio"] if result.get("estimate_ratio") is not None else result["estimate_log"]
    except Exception as exc:  # noqa: BLE001 — a pooling error is itself a defect signal
        return WitnessResult(True, f"pooling failed: {type(exc).__name__}", None)
    deviation = abs(computed - float(claimed))
    if deviation > tol:
        return WitnessResult(True, f"claimed {claimed} vs computed {computed:.5f} (dev {deviation:.5f} > tol {tol})", computed)
    return WitnessResult(False, f"claimed {claimed} ~ computed {computed:.5f}", computed)


def run_witness(task: Task, *, tol: float | None = None) -> WitnessResult:
    """Dispatch to the witness for a task kind. Returns defect=False for kinds
    with no deterministic witness (e.g. DIRECTION) — the panel must catch those."""
    if task.kind == IMPOSSIBLE_CELL:
        return impossible_cell_witness(task.data)
    if task.kind == REPRODUCTION:
        return reproduction_witness(task.data, tol=tol)
    # CLEAN and DIRECTION: no deterministic gate applies (DIRECTION is reviewer-only)
    if task.kind == DIRECTION:
        return WitnessResult(False, "no deterministic witness (reviewer-only defect)")
    return WitnessResult(False, "clean / no witness")
