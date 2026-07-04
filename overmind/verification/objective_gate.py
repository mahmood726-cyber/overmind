"""Objective-gate floor audit (T12a / WORLD_CLASS_SPEC D2).

The single biggest conceptual gap in the harness (per the 2026-07-04 research
doc §1.5 scorecard) is that a ship-eligible verdict can rest on **LLM judges /
consensus agreeing alone**, with no test/build/diff/runtime witness underneath.
That is "two optimists agreeing", not a gate.

This module is the *floor assertion*: given a ``VerificationResult``, classify
whether a **named objective witness** actually contributed to the success
verdict, versus a verdict that leaned on a judge / probabilistic-skip alone.

**It is observational (shadow) by default and NEVER changes a verdict.** The
orchestrator calls ``audit_result`` and emits a ``WOULD-SHIP-WITHOUT-OBJECTIVE-
GATE`` WARN when a success verdict has no objective witness — but the verdict is
returned untouched. Promotion of the WARN to a hard requirement is a later,
measured step (see ROADMAP.md); this module only ever *labels*.

Design:
  * The objective-witness taxonomy is enumerated from the live
    ``VerificationPlanner`` check names (every planner check is command-backed →
    exit-code → objective) plus ``verify_command`` and a Sentinel BLOCK, so it
    stays faithful to what the verifier actually emits.
  * The only *non-objective* deciding checks are the LLM judge
    (``semantic_requirements``) and the probabilistic trajectory fast-path
    (``trajectory_fast_path``) — both are "shipped on opinion / heuristic".
  * A check name the taxonomy does not recognise is reported as ``unknown`` and
    does **not** silently count as an objective floor (fail-closed for the
    audit's purpose), so a new judge-like check surfaces for review rather than
    passing invisibly.

Zero third-party dependencies; pure function core so it is trivially testable
and cannot regress the hot path.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# --- Objective-witness taxonomy -------------------------------------------------
# Every check the VerificationPlanner can emit is command-backed (runs a real
# command, gated on its exit code) — therefore objective. Kept in sync with
# overmind.verification.profiles.VerificationPlanner._commands_for.
_PLANNER_OBJECTIVE_CHECKS: frozenset[str] = frozenset(
    {
        "build",
        "build_or_direct_evidence",
        "relevant_tests",
        "targeted_tests",
        "existing_tests",
        # numeric / methods witnesses (all command-backed test runs)
        "numeric_regression",
        "deterministic_fixture_tests",
        "edge_case_tests",
        "output_comparison",
        "sensitivity_checks",
        "stochastic_stability",
        "calibration_checks",
        "heterogeneity_checks",
        "publication_bias_checks",
        "consistency_checks",
        "ranking_stability",
        "censoring_checks",
        "competing_risks_checks",
        "convergence_checks",
        "posterior_sanity_checks",
        "missing_data_checks",
        "correlation_structure_checks",
        "shape_constraint_checks",
        "temporal_backtest_checks",
        "measurement_error_checks",
        "decision_curve_checks",
        "threshold_stability_checks",
        "identification_checks",
        "variance_component_checks",
        "matrix_stability_checks",
        "distribution_robustness_checks",
        "model_assumption_checks",
        # runtime / browser
        "playwright",
        "targeted_browser_test",
        "smoke_flow",
        "accessibility_check",
        # perf / benchmark
        "lighthouse",
        "before_after_benchmark",
        "no_correctness_regression",
        # regression / parity
        "regression_checks",
        "cross_implementation_parity",
    }
)

# Extra objective witnesses the orchestrator / nightly path can attach that are
# not planner checks but are still command-backed / deterministic gates.
_EXTRA_OBJECTIVE_CHECKS: frozenset[str] = frozenset(
    {
        "verify_command",          # task's own verify command (exit-code gated)
        "sentinel_block",          # Sentinel fail-closed negative gate
        "byte_diff",               # deterministic byte comparison
        "numeric_diff",            # deterministic numeric comparison
        "numerical_continuity",    # numerical-continuity witness
        "r_parity",                # R/metafor parity
        "reproduction",            # independent-reproduction witness (D3)
    }
)

OBJECTIVE_CHECKS: frozenset[str] = _PLANNER_OBJECTIVE_CHECKS | _EXTRA_OBJECTIVE_CHECKS

# Deciding checks that are explicitly NOT an objective gate: shipped on judge
# opinion or a probabilistic heuristic skip.
NON_OBJECTIVE_CHECKS: frozenset[str] = frozenset(
    {
        "semantic_requirements",   # the LLM judge path (orchestrator:780,793)
        "trajectory_fast_path",    # probabilistic completion-probability skip
    }
)

# Prefixes that mark a non-objective check regardless of suffix (defensive).
_NON_OBJECTIVE_PREFIXES: tuple[str, ...] = ("judge", "consensus", "quorum", "semantic")

WARN_LABEL = "WOULD-SHIP-WITHOUT-OBJECTIVE-GATE"


def classify_check(check: str) -> str:
    """Return 'objective' | 'non_objective' | 'unknown' for a single check name.

    A completed check can carry a ``: detail`` suffix in some paths (e.g.
    skipped_checks); only the leading token is classified.
    """
    name = check.split(":", 1)[0].strip().lower()
    if name in OBJECTIVE_CHECKS:
        return "objective"
    if name in NON_OBJECTIVE_CHECKS:
        return "non_objective"
    if any(name.startswith(p) for p in _NON_OBJECTIVE_PREFIXES):
        return "non_objective"
    return "unknown"


@dataclass(slots=True)
class ObjectiveGateAudit:
    """Read-only classification of a verdict's objective-gate posture."""

    task_id: str
    success: bool
    objective_gate_present: bool
    would_ship_without_gate: bool
    objective_checks: list[str] = field(default_factory=list)
    non_objective_checks: list[str] = field(default_factory=list)
    unknown_checks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "success": self.success,
            "objective_gate_present": self.objective_gate_present,
            "would_ship_without_gate": self.would_ship_without_gate,
            "objective_checks": list(self.objective_checks),
            "non_objective_checks": list(self.non_objective_checks),
            "unknown_checks": list(self.unknown_checks),
        }


def audit_checks(task_id: str, success: bool, completed_checks: list[str]) -> ObjectiveGateAudit:
    """Classify a verdict from its completed checks. Pure — no side effects.

    ``would_ship_without_gate`` is True iff the verdict is a *success* AND no
    completed check is an objective witness. Unknown checks do NOT count as an
    objective floor (fail-closed for the audit), so a judge-only or
    heuristic-only success is flagged.
    """
    objective: list[str] = []
    non_objective: list[str] = []
    unknown: list[str] = []
    for check in completed_checks:
        kind = classify_check(check)
        if kind == "objective":
            objective.append(check)
        elif kind == "non_objective":
            non_objective.append(check)
        else:
            unknown.append(check)

    gate_present = len(objective) > 0
    return ObjectiveGateAudit(
        task_id=task_id,
        success=success,
        objective_gate_present=gate_present,
        would_ship_without_gate=bool(success and not gate_present),
        objective_checks=objective,
        non_objective_checks=non_objective,
        unknown_checks=unknown,
    )


def audit_result(result: object) -> ObjectiveGateAudit:
    """Audit a ``VerificationResult``-shaped object (has ``.task_id``,
    ``.success``, ``.completed_checks``)."""
    return audit_checks(
        task_id=getattr(result, "task_id", ""),
        success=bool(getattr(result, "success", False)),
        completed_checks=list(getattr(result, "completed_checks", []) or []),
    )


def audit_mode() -> str:
    """Current audit mode from ``OVERMIND_OBJECTIVE_GATE_AUDIT``.

    'off'    — do nothing (no classification call sites should run).
    'shadow' — classify + WARN-log, never change a verdict (DEFAULT).
    'strict' — reserved for a future promoted mode; today behaves like 'shadow'
               at the emit layer (this module never mutates a verdict — promotion
               logic, when it lands, lives in the caller behind its own flag).
    """
    raw = os.environ.get("OVERMIND_OBJECTIVE_GATE_AUDIT", "shadow").strip().lower()
    if raw in {"off", "0", "false", "no"}:
        return "off"
    if raw in {"strict"}:
        return "strict"
    return "shadow"


def emit_audit(result: object, *, logger_: logging.Logger | None = None) -> ObjectiveGateAudit | None:
    """Shadow entry point for the orchestrator. Classifies the verdict and emits
    a WARN when it would ship without an objective gate. Returns the audit (or
    ``None`` if the audit is disabled). **Never mutates the verdict.**
    """
    if audit_mode() == "off":
        return None
    audit = audit_result(result)
    log = logger_ or logger
    if audit.would_ship_without_gate:
        log.warning(
            "%s task=%s: success verdict has no objective witness "
            "(non_objective=%s unknown=%s) — shipping on opinion, not proof",
            WARN_LABEL,
            audit.task_id,
            audit.non_objective_checks or "none",
            audit.unknown_checks or "none",
        )
    return audit
