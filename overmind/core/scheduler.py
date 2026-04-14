from __future__ import annotations

from typing import TYPE_CHECKING

from overmind.config import PoliciesConfig
from overmind.storage.models import Assignment, ProjectRecord, RunnerRecord, TaskRecord

if TYPE_CHECKING:
    from overmind.runners.q_router import QRouter


class Scheduler:
    def __init__(self, policies: PoliciesConfig, q_router: QRouter | None = None) -> None:
        self.policies = policies
        self.q_router = q_router

    def assign(
        self,
        tasks: list[TaskRecord],
        runners: list[RunnerRecord],
        projects: dict[str, ProjectRecord],
        capacity: int,
        prompt_builder,
    ) -> list[Assignment]:
        available_runners = [runner for runner in runners if runner.status == "AVAILABLE" and runner.available]
        queued_tasks = sorted(tasks, key=lambda task: task.priority, reverse=True)
        assignments: list[Assignment] = []

        for task in queued_tasks:
            if len(assignments) >= capacity:
                break
            if not available_runners:
                break
            project = projects.get(task.project_id)
            if not project:
                continue
            eligible_runners = [runner for runner in available_runners if self._runner_is_eligible(runner, task)]
            if not eligible_runners:
                continue
            best_runner = max(
                eligible_runners,
                key=lambda runner: self._runner_score(runner, task),
            )
            assignments.append(
                Assignment(
                    runner_id=best_runner.runner_id,
                    task_id=task.task_id,
                    project_id=task.project_id,
                    prompt=prompt_builder(project, task),
                    trace_id=task.trace_id or task.task_id,
                    requires_isolation=self._requires_isolated_workspace(task),
                )
            )
            available_runners.remove(best_runner)
        return assignments

    def _runner_is_eligible(self, runner: RunnerRecord, task: TaskRecord) -> bool:
        if self._requires_isolated_runner(task) and not runner.isolated:
            return False
        return True

    def _requires_isolated_workspace(self, task: TaskRecord) -> bool:
        mode = str(self.policies.isolation.get("mode", "none")).strip().lower()
        if mode in {"strict", "strict_worktree"}:
            return True
        if mode in {"worktree", "high_risk_worktree", "high-risk-worktree"}:
            return task.risk.startswith("high")
        return False

    def _requires_isolated_runner(self, task: TaskRecord) -> bool:
        mode = str(self.policies.isolation.get("mode", "none")).strip().lower()
        if mode in {"", "none", "off", "disabled"}:
            return False
        if mode == "strict":
            return True
        if mode in {"high_risk", "high-risk", "require_high_risk"}:
            return task.risk.startswith("high")
        return False

    def _runner_score(self, runner: RunnerRecord, task: TaskRecord) -> float:
        strengths = self.policies.strengths_for(runner.runner_type)
        score = runner.success_rate_7d - runner.failure_rate_7d
        if task.task_type in {"verification", "test_writing"} and "tests" in strengths:
            score += 0.4
        if task.task_type == "implementation" and any(
            strength in strengths for strength in ("targeted_fix", "cleanup")
        ):
            score += 0.4
        if task.task_type == "performance_optimization" and "benchmarks" in strengths:
            score += 0.4
        if task.task_type in {"architecture", "refactor"} and "architecture" in strengths:
            score += 0.4
        if task.risk.startswith("high") and runner.runner_type == "claude":
            score += 0.2
        score -= min(runner.avg_latency_sec / 120.0, 0.3)
        if self.q_router is not None:
            score += self.q_router.score(runner.runner_type, task.task_type) * 0.5
        return score
