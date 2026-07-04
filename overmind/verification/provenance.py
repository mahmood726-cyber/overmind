"""Per-verdict provenance recording at the Dispatch accept point (D7 / D4 / D2).

WORLD_CLASS_SPEC D7 makes Dispatch the single control plane: every accept passes
through one instrumented conductor that records *which vendor produced the work,
which gate decided it, and whether an objective witness sat under the pass*. This
module is the harness-side realization of that record.

It composes the objective-gate floor audit (``objective_gate.audit_result``) with
the vendor that did the work and (optionally) the cross-vendor check + cost, and
appends an **append-only JSONL** line per verdict. A ``summarize`` pass over that
stream is the **WARN-cycle quantifier**: "N of M success verdicts had an objective
witness; K would ship on judge/consensus alone" — the number §3/Step-1 needs to
decide whether to promote the objective-gate floor from WARN to a hard gate.

Design:
  * SHADOW / observational — recording never changes a verdict. Wrapped by the
    caller so a recorder bug can never wedge the accept path.
  * Gated by ``OVERMIND_PROVENANCE`` (default 'off'); when 'on'/'shadow' the
    recorder appends to ``OVERMIND_PROVENANCE_PATH`` or a caller-supplied path.
  * Pure dataclasses + a stateless summarizer so the quantifier is trivially
    testable without running the orchestrator.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from overmind.verification.objective_gate import ObjectiveGateAudit, audit_result

logger = logging.getLogger(__name__)


def provenance_mode() -> str:
    """'off' (default) | 'shadow' (record, never change a verdict)."""
    raw = os.environ.get("OVERMIND_PROVENANCE", "off").strip().lower()
    if raw in {"shadow", "on", "1", "true", "yes"}:
        return "shadow"
    return "off"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class VerdictProvenance:
    """One accept-point provenance record (D7)."""

    task_id: str
    success: bool
    # objective-gate floor (D2)
    objective_gate_present: bool
    would_ship_without_gate: bool
    objective_checks: list[str] = field(default_factory=list)
    non_objective_checks: list[str] = field(default_factory=list)
    unknown_checks: list[str] = field(default_factory=list)
    # who produced the work (D7)
    worker_runner: str = ""            # runner_type that did the work (e.g. 'claude')
    worker_family: str = ""            # model family (anthropic / openai / google)
    judge_vendors: list[str] = field(default_factory=list)  # configured judge panel
    # cross-vendor check (D1) — optional enrichment
    cross_vendor_present: bool = False
    cross_vendor_decorrelated: bool | None = None
    cross_vendor_engine: str | None = None
    # economics (D5) — optional enrichment
    cost_usd: float | None = None
    # context
    project_id: str = ""
    trace_id: str = ""
    recorded_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "project_id": self.project_id,
            "success": self.success,
            "objective_gate_present": self.objective_gate_present,
            "would_ship_without_gate": self.would_ship_without_gate,
            "objective_checks": list(self.objective_checks),
            "non_objective_checks": list(self.non_objective_checks),
            "unknown_checks": list(self.unknown_checks),
            "worker_runner": self.worker_runner,
            "worker_family": self.worker_family,
            "judge_vendors": list(self.judge_vendors),
            "cross_vendor_present": self.cross_vendor_present,
            "cross_vendor_decorrelated": self.cross_vendor_decorrelated,
            "cross_vendor_engine": self.cross_vendor_engine,
            "cost_usd": self.cost_usd,
            "trace_id": self.trace_id,
            "recorded_at": self.recorded_at,
        }


def _family_for(runner: str) -> str:
    """Map a runner_type / engine name to its model family (best-effort)."""
    if not runner:
        return ""
    try:
        from overmind.verification.judge_factory import family_for_engine
        return family_for_engine(runner)
    except Exception:  # noqa: BLE001 — provenance must never hard-fail
        return runner.strip().lower()


def configured_judge_vendors() -> list[str]:
    """The judge panel families configured via OVERMIND_JUDGE_ENGINE (best-effort)."""
    raw = os.environ.get("OVERMIND_JUDGE_ENGINE", "").strip()
    if not raw:
        return []
    return [_family_for(e) for e in (part.strip() for part in raw.split(",")) if e]


def build_provenance(
    result: object,
    *,
    worker_runner: str = "",
    project_id: str = "",
    judge_vendors: list[str] | None = None,
    cross_vendor: object | None = None,
    cost_usd: float | None = None,
) -> VerdictProvenance:
    """Compose a provenance record from a ``VerificationResult`` + optional
    enrichments. Derives the objective-gate posture via the audit taxonomy."""
    audit: ObjectiveGateAudit = audit_result(result)
    cv_present = False
    cv_decorrelated: bool | None = None
    cv_engine: str | None = None
    if cross_vendor is not None:
        cv_present = bool(getattr(cross_vendor, "present", False))
        cv_decorrelated = getattr(cross_vendor, "decorrelated", None)
        cv_engine = getattr(cross_vendor, "checker_engine", None)
    return VerdictProvenance(
        task_id=audit.task_id,
        success=audit.success,
        objective_gate_present=audit.objective_gate_present,
        would_ship_without_gate=audit.would_ship_without_gate,
        objective_checks=audit.objective_checks,
        non_objective_checks=audit.non_objective_checks,
        unknown_checks=audit.unknown_checks,
        worker_runner=worker_runner,
        worker_family=_family_for(worker_runner),
        judge_vendors=judge_vendors if judge_vendors is not None else configured_judge_vendors(),
        cross_vendor_present=cv_present,
        cross_vendor_decorrelated=cv_decorrelated,
        cross_vendor_engine=cv_engine,
        cost_usd=cost_usd,
        project_id=project_id,
        trace_id=str(getattr(result, "trace_id", "") or ""),
    )


class ProvenanceRecorder:
    """Appends verdict-provenance records to an append-only JSONL."""

    def __init__(self, jsonl_path: Path | str) -> None:
        self.jsonl_path = Path(jsonl_path)

    def record(self, prov: VerdictProvenance) -> None:
        try:
            self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            with self.jsonl_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(prov.to_dict()) + "\n")
        except OSError as exc:  # best-effort; never break the accept path
            logger.warning("provenance record write failed: %s", exc)


def resolve_recorder(default_path: Path | str | None = None) -> ProvenanceRecorder | None:
    """Build a recorder honoring the flag + path env. Returns None when disabled."""
    if provenance_mode() == "off":
        return None
    path = os.environ.get("OVERMIND_PROVENANCE_PATH") or default_path
    if not path:
        return None
    return ProvenanceRecorder(path)


# --- WARN-cycle quantifier ------------------------------------------------------

@dataclass(slots=True)
class ProvenanceSummary:
    """Aggregate posture over a stream of provenance records (the WARN tally)."""

    total: int = 0
    successes: int = 0
    with_objective_gate: int = 0
    would_ship_without_gate: int = 0
    with_cross_vendor: int = 0
    decorrelated_cross_vendor: int = 0
    total_cost_usd: float = 0.0
    worker_families: dict[str, int] = field(default_factory=dict)

    @property
    def pct_success_on_consensus_only(self) -> float | None:
        """% of *success* verdicts that would ship without an objective gate."""
        if self.successes == 0:
            return None
        return round(100.0 * self.would_ship_without_gate / self.successes, 2)

    def headline(self) -> str:
        pct = self.pct_success_on_consensus_only
        pct_s = "n/a" if pct is None else f"{pct}%"
        return (
            f"provenance: {self.successes}/{self.total} success verdicts; "
            f"{self.with_objective_gate} had an objective witness; "
            f"{self.would_ship_without_gate} would ship on consensus alone ({pct_s}); "
            f"cross-vendor present on {self.with_cross_vendor}"
        )

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "successes": self.successes,
            "with_objective_gate": self.with_objective_gate,
            "would_ship_without_gate": self.would_ship_without_gate,
            "pct_success_on_consensus_only": self.pct_success_on_consensus_only,
            "with_cross_vendor": self.with_cross_vendor,
            "decorrelated_cross_vendor": self.decorrelated_cross_vendor,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "worker_families": dict(self.worker_families),
        }


def summarize_records(records: Iterable[dict]) -> ProvenanceSummary:
    """Fold a stream of provenance dicts into the WARN-cycle tally."""
    s = ProvenanceSummary()
    for rec in records:
        s.total += 1
        if rec.get("success"):
            s.successes += 1
            if rec.get("objective_gate_present"):
                s.with_objective_gate += 1
            if rec.get("would_ship_without_gate"):
                s.would_ship_without_gate += 1
        if rec.get("cross_vendor_present"):
            s.with_cross_vendor += 1
            if rec.get("cross_vendor_decorrelated"):
                s.decorrelated_cross_vendor += 1
        cost = rec.get("cost_usd")
        if isinstance(cost, (int, float)):
            s.total_cost_usd += float(cost)
        fam = rec.get("worker_family") or ""
        if fam:
            s.worker_families[fam] = s.worker_families.get(fam, 0) + 1
    return s


def summarize_file(jsonl_path: Path | str) -> ProvenanceSummary:
    """Summarize a provenance JSONL file (skips malformed lines)."""
    path = Path(jsonl_path)
    if not path.exists():
        return ProvenanceSummary()

    def _iter():
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    return summarize_records(_iter())
