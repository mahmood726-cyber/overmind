"""Benchmark runner: drive an arm over a held-out slice with checkpoint/resume
and cost attribution (§3).

Uses the reliability CheckpointStore so a killed run resumes (per-task), and the
telemetry CostLedger so cost-per-accepted-change comes from the real cost
instrument. Each arm run is a loop with an objective gate (the witness, for C),
a stop (task list exhausted), and external state (checkpoint + results JSONL).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from overmind.benchmark.arms import ArmVerdict, arm_a, arm_b, arm_c
from overmind.benchmark.tasks import Task
from overmind.benchmark.witnesses import run_witness
from overmind.reliability.checkpoint import CheckpointStore
from overmind.telemetry.cost_accounting import CostLedger

# A reviewer callable: Task -> ReviewerVerdict.
Reviewer = Callable[[Task], object]
# A cost estimator: (Task, ReviewerVerdict) -> usd (real total_cost_usd or estimate).
CostFn = Callable[[Task, object], float]


@dataclass(slots=True)
class ArmSpec:
    name: str                      # "A" | "B" | "C"
    reviewers: list                # list of reviewer callables
    use_witness: bool = False      # C uses the objective-gate floor

    def aggregate(self, task: Task, reviewer_verdicts: list, witness_defect: bool) -> ArmVerdict:
        if self.name == "A":
            return arm_a(task.id, reviewer_verdicts)
        if self.name == "B":
            return arm_b(task.id, reviewer_verdicts)
        return arm_c(task.id, reviewer_verdicts, witness_defect)


@dataclass(slots=True)
class ArmRun:
    arm: str
    verdicts: dict = field(default_factory=dict)     # task_id -> ArmVerdict
    costs: dict = field(default_factory=dict)         # task_id -> usd
    reviewer_records: dict = field(default_factory=dict)


def run_arm(
    spec: ArmSpec,
    tasks: list[Task],
    *,
    checkpoint_store: CheckpointStore | None = None,
    cost_ledger: CostLedger | None = None,
    cost_fn: CostFn | None = None,
    results_path: Path | str | None = None,
) -> ArmRun:
    """Run one arm over ``tasks``, resuming from the checkpoint if present."""
    run = ArmRun(arm=spec.name)
    loop = f"benchmark-arm-{spec.name}"

    # resume: load any prior verdicts from the results JSONL so a kill mid-run
    # doesn't lose completed tasks.
    done_ids: set[str] = set()
    if results_path and Path(results_path).exists():
        for line in Path(results_path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("arm") == spec.name:
                done_ids.add(rec["task_id"])
                run.verdicts[rec["task_id"]] = _verdict_from_dict(rec)
                run.costs[rec["task_id"]] = float(rec.get("cost_usd", 0.0))

    todo = tasks
    if checkpoint_store is not None:
        remaining = set(checkpoint_store.remaining(loop, [t.id for t in tasks]))
        todo = [t for t in tasks if t.id in remaining and t.id not in done_ids]
    else:
        todo = [t for t in tasks if t.id not in done_ids]

    for task in todo:
        reviewer_verdicts = [rv(task) for rv in spec.reviewers]
        witness_defect = False
        if spec.use_witness:
            witness_defect = run_witness(task).defect
        verdict = spec.aggregate(task, reviewer_verdicts, witness_defect)

        cost = 0.0
        if cost_fn is not None:
            cost = sum(cost_fn(task, rv) for rv in reviewer_verdicts)
        run.verdicts[task.id] = verdict
        run.costs[task.id] = cost
        run.reviewer_records[task.id] = [getattr(rv, "to_dict", lambda: {})() for rv in reviewer_verdicts]

        if cost_ledger is not None:
            from overmind.telemetry.cost_accounting import CostEvent
            cost_ledger.add_cost(CostEvent(loop=loop, engine=spec.name, usd=cost, measured=False))
            cost_ledger.record_decision(verdict.accepted, loop=loop)

        if results_path:
            _append_result(results_path, task, verdict, cost, run.reviewer_records[task.id])
        if checkpoint_store is not None:
            checkpoint_store.mark_done(loop, task.id)

    return run


def _append_result(path: Path | str, task: Task, verdict: ArmVerdict, cost: float, reviewers: list) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {**verdict.to_dict(), "kind": task.kind, "cost_usd": cost, "reviewers": reviewers}
    with p.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(rec) + "\n")


def _verdict_from_dict(rec: dict) -> ArmVerdict:
    return ArmVerdict(
        task_id=rec["task_id"], arm=rec["arm"], flag=bool(rec["flag"]),
        accepted=bool(rec["accepted"]), deciding=rec.get("deciding", ""),
        reviewer_flags=list(rec.get("reviewer_flags", [])), witness_defect=rec.get("witness_defect"),
    )
