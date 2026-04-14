from __future__ import annotations

import json
import time
from pathlib import Path

from overmind.intelligence.daily_report import DailyReport
from overmind.storage.models import utc_now


class EvalHarness:
    def __init__(self, orchestrator, artifacts_dir: Path) -> None:
        self.orchestrator = orchestrator
        self.artifacts_dir = artifacts_dir
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def run(self, focus_project_id: str | None = None) -> dict[str, object]:
        timings_ms: dict[str, int] = {}

        start = time.perf_counter()
        scan = self.orchestrator.scan(focus_project_id=focus_project_id)
        timings_ms["scan"] = round((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        dry_run = self.orchestrator.run_once(
            focus_project_id=focus_project_id,
            settle_seconds=0,
            dry_run=True,
        )
        timings_ms["run_once_dry_run"] = round((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        state = self.orchestrator.show_state(focus_project_id=focus_project_id)
        timings_ms["show_state"] = round((time.perf_counter() - start) * 1000)

        projects = self.orchestrator.db.list_projects()
        memories = self.orchestrator.db.list_memories(limit=10000)
        routing_scores = self.orchestrator.db.list_routing_scores()
        benchmark = DailyReport(
            self.orchestrator.db,
            self.artifacts_dir,
        )._benchmark_tracking(projects, memories, routing_scores)

        report = {
            "generated_at": utc_now(),
            "focus_project_id": focus_project_id,
            "isolation_policy": dict(self.orchestrator.config.policies.isolation),
            "runner_inventory": {
                "total": len(scan["runners"]),
                "isolated": sum(1 for runner in scan["runners"] if runner.get("isolated")),
                "available": sum(1 for runner in scan["runners"] if runner.get("status") == "AVAILABLE"),
            },
            "scan": {
                "project_count": scan["project_count"],
                "runner_count": scan["runner_count"],
            },
            "dispatch": {
                "desired_sessions": dry_run["desired_sessions"],
                "generated_tasks": dry_run["generated_tasks"],
                "would_dispatch_count": len(dry_run["would_dispatch"]),
                "would_dispatch": dry_run["would_dispatch"],
            },
            "state": {
                "project_count": len(state["projects"]),
                "task_count": len(state["tasks"]),
                "insight_count": len(state["insights"]),
                "checkpoint_present": state["checkpoint"] is not None,
            },
            "checkpoint_history": self.orchestrator.list_checkpoints(name="main", limit=5)["checkpoints"],
            "benchmark": benchmark,
            "timings_ms": timings_ms,
        }
        artifact_path = self.write(report, focus_project_id=focus_project_id)
        report["artifact"] = str(artifact_path)
        return report

    def write(self, report: dict[str, object], focus_project_id: str | None = None) -> Path:
        suffix = focus_project_id or "portfolio"
        path = self.artifacts_dir / f"eval_harness_{suffix}.json"
        path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        return path
