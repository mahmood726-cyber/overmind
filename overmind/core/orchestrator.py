from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from overmind.subprocess_utils import (
    kill_process_tree,
    split_command,
    validate_command_prefix_with_detail,
    verifier_popen_kwargs,
)

from overmind.config import AppConfig
from overmind.core.health_manager import HealthManager
from overmind.core.policy_engine import PolicyEngine
from overmind.core.scheduler import Scheduler
from overmind.discovery.indexer import ProjectIndexer
from overmind.discovery.portfolio_audit import PortfolioAuditor
from overmind.isolation.worktree_manager import WorktreeManager
from overmind.memory.audit_loop import AuditLoop
from overmind.memory.dream_engine import DreamEngine
from overmind.memory.extractor import MemoryExtractor
from overmind.memory.insights import InsightEngine
from overmind.memory.store import MemoryStore
from overmind.parsing.terminal_parser import TerminalParser
from overmind.runners.protocols import RunnerProtocol
from overmind.runners.q_router import QRouter
from overmind.runners.runner_registry import RunnerRegistry
from overmind.sessions.session_manager import SessionManager
from overmind.storage.db import StateDatabase
from overmind.storage.models import InsightRecord, ProjectRecord, RunnerRecord, TaskRecord, VerificationResult
from overmind.tasks.prioritizer import Prioritizer
from overmind.tasks.task_generator import TaskGenerator
from overmind.tasks.task_models import build_baseline_task
from overmind.tasks.task_queue import TaskQueue
from overmind.verification.llm_judge import GeminiBackend, LLMJudge
from overmind.verification.policy_guard import PolicyGuard
from overmind.verification.trajectory_scorer import TrajectoryScorer
from overmind.verification.verifier import VerificationEngine


class Orchestrator:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.db = StateDatabase(config.db_path)
        self.indexer = ProjectIndexer(config, self.db)
        self.portfolio_auditor = PortfolioAuditor(config.data_dir / "artifacts")
        self.runner_registry = RunnerRegistry(config, self.db)
        self.task_queue = TaskQueue(self.db)
        self.health_manager = HealthManager()
        self.policy_engine = PolicyEngine(config.policies)
        self.q_router = QRouter(self.db)
        self.scheduler = Scheduler(config.policies, q_router=self.q_router)
        self.task_generator = TaskGenerator()
        self.prioritizer = Prioritizer()
        self.policy_guard = PolicyGuard()
        self.worktree_manager = WorktreeManager(config.data_dir / "worktrees")
        self.session_manager = SessionManager(
            config.data_dir / "transcripts",
            output_blocker=self._blocking_policy_message,
            worktree_manager=self.worktree_manager,
            isolation_mode=str(config.policies.isolation.get("mode", "none")),
        )
        self.parser = TerminalParser(
            summary_trigger_lines=int(config.policies.limits.get("summary_trigger_output_lines", 400)),
            idle_timeout_min=int(config.policies.limits.get("idle_timeout_min", 10)),
        )
        self.verifier = VerificationEngine(config.data_dir / "artifacts")
        self.trajectory_scorer = TrajectoryScorer()
        self.llm_judge = self._build_llm_judge()
        self.memory_store = MemoryStore(
            db=self.db,
            checkpoints_dir=config.data_dir / "checkpoints",
            logs_dir=config.data_dir / "logs",
        )
        self.insight_engine = InsightEngine()
        self.memory_extractor = MemoryExtractor(self.db)
        self.dream_engine = DreamEngine(self.db)
        self.audit_loop = AuditLoop(self.db)
        self.tick_count = 0
        prompts_dir = Path(__file__).resolve().parents[1] / "prompts"
        self.worker_prompt_template = (prompts_dir / "worker_prompt.txt").read_text(encoding="utf-8")
        self.critique_prompt = (prompts_dir / "critique_prompt.txt").read_text(encoding="utf-8")
        self._recover_abandoned_tasks()
        self.memory_store.decay_all(0.95)
        self.memory_store.archive_stale(0.1)

    def close(self) -> None:
        self.session_manager.reconcile(0)
        self.db.close()

    def scan(self, focus_project_id: str | None = None) -> dict[str, object]:
        projects = self.indexer.incremental_refresh(focus_project_id)
        runners = self.runner_registry.refresh(self.session_manager.active_assignments())
        return {
            "project_count": len(projects),
            "runner_count": len(runners),
            "projects": [project.to_dict() for project in projects],
            "runners": [runner.to_dict() for runner in runners],
        }

    def portfolio_audit(self, focus_project_id: str | None = None) -> dict[str, object]:
        projects = self.indexer.incremental_refresh(focus_project_id)
        report = self.portfolio_auditor.build_report(projects)
        artifact_paths = self.portfolio_auditor.write_report(report)
        return {
            "report": report,
            "artifacts": artifact_paths,
        }

    def enqueue_demo(self, project_id: str) -> TaskRecord:
        project = self.db.get_project(project_id)
        if not project:
            raise KeyError(f"Unknown project {project_id}")
        task = build_baseline_task(project)
        self.task_queue.upsert([task])
        return task

    def run_once(self, focus_project_id: str | None = None, settle_seconds: float = 0.75, dry_run: bool = False) -> dict[str, object]:
        machine = self.health_manager.snapshot(self.session_manager.active_count())
        active_assignments = self.session_manager.active_assignments()
        runners = self.runner_registry.refresh(active_assignments)
        available_runner_count = len([runner for runner in runners if runner.available])
        projects = self.indexer.incremental_refresh(focus_project_id)
        project_map = {project.project_id: project for project in self.db.list_projects()}

        existing_tasks = self.task_queue.list_all()
        generated_tasks = self.task_generator.generate(projects, existing_tasks)
        self.task_queue.upsert(generated_tasks)

        queued_tasks = self.prioritizer.reprioritize(self.task_queue.queued(), project_map)
        if focus_project_id:
            queued_tasks = [task for task in queued_tasks if task.project_id == focus_project_id]
        desired_sessions = self.policy_engine.compute_concurrency(machine, available_runner_count)
        self.session_manager.reconcile(desired_sessions)
        capacity = max(0, desired_sessions - self.session_manager.active_count())

        assignments = self.scheduler.assign(
            tasks=queued_tasks,
            runners=runners,
            projects=project_map,
            capacity=capacity,
            prompt_builder=self._build_worker_prompt,
        )
        if dry_run:
            return {
                "dry_run": True,
                "projects_indexed": len(projects),
                "generated_tasks": len(generated_tasks),
                "would_dispatch": [assignment.to_dict() for assignment in assignments],
                "desired_sessions": desired_sessions,
            }
        for assignment in assignments:
            self.task_queue.transition(
                assignment.task_id,
                "ASSIGNED",
                assigned_runner_id=assignment.runner_id,
            )

        runner_protocols: dict[str, RunnerProtocol] = {}
        for runner in runners:
            adapter = self.runner_registry.adapter_for(runner.runner_id)
            if adapter:
                runner_protocols[runner.runner_id] = adapter.protocol()

        started_task_ids = set(
            self.session_manager.dispatch(
                assignments=assignments,
                runners={runner.runner_id: runner for runner in runners},
                projects=project_map,
                protocols=runner_protocols,
            )
        )
        for assignment in assignments:
            if assignment.task_id in started_task_ids:
                self.task_queue.transition(
                    assignment.task_id,
                    "RUNNING",
                    assigned_runner_id=assignment.runner_id,
                )

        if settle_seconds > 0 and (started_task_ids or self.session_manager.active_count()):
            time.sleep(settle_seconds)

        observations = self.session_manager.collect_output()
        evidence_items = self.parser.parse(observations)
        observation_map = {observation.task_id: observation for observation in observations}
        policy_violations_by_task = {}
        for evidence in evidence_items:
            observation = observation_map.get(evidence.task_id)
            policy_lines = observation.lines if observation and observation.lines else evidence.output_excerpt
            policy_violations_by_task[evidence.task_id] = (
                self.policy_guard.evaluate(policy_lines) if policy_lines else []
            )
        interventions = self._decide_interventions(evidence_items, policy_violations_by_task)
        self.session_manager.apply_interventions(interventions)

        verification_results = []
        for evidence in evidence_items:
            task = self.db.get_task(evidence.task_id)
            if not task:
                continue
            observation = observation_map.get(evidence.task_id)
            runtime = observation.runtime_seconds if observation else 0.0
            output_lines = observation.lines if observation else []
            policy_violations = policy_violations_by_task.get(evidence.task_id, [])

            if self.policy_guard.has_blocks(policy_violations):
                violation_messages = [
                    f"{violation.rule_name}: {violation.message}"
                    for violation in policy_violations
                    if violation.severity == "block"
                ]
                self.task_queue.transition(
                    evidence.task_id,
                    "NEEDS_INTERVENTION",
                    last_error="; ".join(violation_messages) or "policy violation detected",
                )
                self.runner_registry.update_outcome(
                    evidence.runner_id,
                    success=False,
                    latency_sec=runtime,
                    output_lines=output_lines,
                )
                runner_record = self.db.get_runner(evidence.runner_id)
                if runner_record:
                    self.q_router.record(runner_record.runner_type, task.task_type, False)
                continue

            if evidence.state == "NEEDS_INTERVENTION":
                self.task_queue.transition(
                    evidence.task_id,
                    "NEEDS_INTERVENTION",
                    last_error="; ".join(evidence.risks) or "intervention required",
                )
                if evidence.exited:
                    self.runner_registry.update_outcome(
                        evidence.runner_id,
                        success=False,
                        latency_sec=runtime,
                        output_lines=output_lines,
                    )
                    runner_record = self.db.get_runner(evidence.runner_id)
                    if runner_record:
                        self.q_router.record(runner_record.runner_type, task.task_type, False)
                continue

            if evidence.exited and evidence.exit_code == 0:
                # TrajectoryScorer: estimate completion probability before expensive verification
                trajectory = self.trajectory_scorer.score(evidence, output_lines)
                if trajectory.recommendation == "retry":
                    self.task_queue.transition(
                        evidence.task_id,
                        "FAILED",
                        last_error=f"Trajectory score too low ({trajectory.completion_probability:.2f}): "
                                   f"{', '.join(k for k, v in trajectory.signals.items() if v < 0)}",
                    )
                    self.runner_registry.update_outcome(
                        evidence.runner_id, success=False, latency_sec=runtime, output_lines=output_lines,
                    )
                    runner_record = self.db.get_runner(evidence.runner_id)
                    if runner_record:
                        self.q_router.record(runner_record.runner_type, task.task_type, False)
                    continue

                self.task_queue.transition(evidence.task_id, "VERIFYING")
                project = project_map.get(task.project_id)
                if not project:
                    self.task_queue.transition(
                        evidence.task_id,
                        "FAILED",
                        last_error="project missing from index",
                    )
                    continue
                result = self.verifier.run(task, project)
                final_result = self._apply_completion_gates(
                    task=task,
                    project=project,
                    verification_result=result,
                    transcript_lines=output_lines,
                    include_judge=True,
                )
                verification_results.append(final_result)
                if final_result.success:
                    self.task_queue.transition(
                        evidence.task_id,
                        "COMPLETED",
                        verification_summary=final_result.details,
                    )
                else:
                    self.task_queue.transition(
                        evidence.task_id,
                        "FAILED",
                        last_error="; ".join(final_result.details + final_result.skipped_checks),
                        verification_summary=final_result.details,
                    )
                self.runner_registry.update_outcome(
                    evidence.runner_id,
                    success=final_result.success,
                    latency_sec=runtime,
                    output_lines=output_lines,
                )
                runner_record = self.db.get_runner(evidence.runner_id)
                if runner_record:
                    self.q_router.record(runner_record.runner_type, task.task_type, final_result.success)
                self.audit_loop.evaluate(
                    project_id=task.project_id,
                    result=final_result,
                    tick=self.tick_count,
                )

        insights = self.insight_engine.extract(evidence_items, verification_results)
        self.memory_store.save_insights(insights)

        self.tick_count += 1
        all_project_ids = {task.task_id: task.project_id for task in self.db.list_tasks()}
        all_runner_ids = {
            assignment.task_id: assignment.runner_id for assignment in assignments
        }
        extracted_memories = self.memory_extractor.extract(
            evidence_items=evidence_items,
            verification_results=verification_results,
            project_ids=all_project_ids,
            runner_ids=all_runner_ids,
            tick=self.tick_count,
        )

        checkpoint_payload = {
            "machine": machine.to_dict(),
            "desired_sessions": desired_sessions,
            "projects": [project.to_dict() for project in projects],
            "runners": [runner.to_dict() for runner in self.db.list_runners()],
            "tasks": [task.to_dict() for task in self.db.list_tasks()],
            "evidence": [item.to_dict() for item in evidence_items],
            "insights": [item.to_dict() for item in insights],
            "interventions": interventions,
            "memories_extracted": len(extracted_memories),
        }
        checkpoint_id = self.memory_store.write_checkpoint("main", checkpoint_payload)

        active_memory_count = len(self.memory_store.list_all(status="active"))
        if self.dream_engine.should_dream(self.tick_count, active_memory_count):
            # Swallow dream failures — consolidation is a best-effort optimisation;
            # a bug in the dream engine must not keep triggering on every tick.
            try:
                self.dream_engine.dream()
            except Exception:  # noqa: BLE001 — background optimisation, not critical path
                pass
            self.tick_count = 0

        return {
            "projects_indexed": len(projects),
            "generated_tasks": len(generated_tasks),
            "assignments": [assignment.to_dict() for assignment in assignments],
            "observations": [observation.to_dict() for observation in observations],
            "evidence": [item.to_dict() for item in evidence_items],
            "insights": [item.to_dict() for item in insights],
            "desired_sessions": desired_sessions,
            "memories_extracted": len(extracted_memories),
            "checkpoint_id": checkpoint_id,
        }

    _RUN_LOOP_HISTORY_CAP = 100

    def run_loop(
        self,
        iterations: int | None = None,
        sleep_seconds: float = 5.0,
        focus_project_id: str | None = None,
    ) -> dict[str, object]:
        history: list[dict[str, object]] = []
        iteration = 0
        interrupted = False
        try:
            while iterations is None or iteration < iterations:
                history.append(self.run_once(focus_project_id=focus_project_id))
                # Cap history to avoid unbounded memory growth in long-running loops.
                if len(history) > self._RUN_LOOP_HISTORY_CAP:
                    del history[: len(history) - self._RUN_LOOP_HISTORY_CAP]
                iteration += 1
                if iterations is not None and iteration >= iterations:
                    break
                time.sleep(sleep_seconds)
        except KeyboardInterrupt:
            # Graceful shutdown: reconcile active sessions so we don't orphan
            # subprocesses or leave tasks stuck in ASSIGNED / RUNNING state.
            interrupted = True
            self.session_manager.reconcile(0)
        return {"iterations": history, "iterations_run": iteration, "interrupted": interrupted}

    def list_checkpoints(self, name: str | None = None, limit: int = 20) -> dict[str, object]:
        checkpoints = self.db.list_checkpoints(name=name, limit=limit)
        return {
            "checkpoints": [
                {
                    "id": checkpoint["id"],
                    "name": checkpoint["name"],
                    "created_at": checkpoint["created_at"],
                    "keys": sorted(checkpoint["payload"].keys()),
                }
                for checkpoint in checkpoints
            ]
        }

    def restore_checkpoint(
        self,
        checkpoint_id: int | None = None,
        checkpoint_name: str = "main",
        focus_project_id: str | None = None,
        force: bool = False,
    ) -> dict[str, object]:
        checkpoint_record = self._resolve_checkpoint_record(checkpoint_id, checkpoint_name)
        if checkpoint_record is None:
            return {
                "checkpoint_id": checkpoint_id,
                "checkpoint_name": checkpoint_name,
                "restored": False,
                "restored_counts": {},
                "restored_checkpoint_id": None,
            }

        # Guard: restoring a checkpoint terminates all active sessions. If work
        # is in flight, require explicit --force so we don't silently discard
        # agent progress.
        active = self.session_manager.active_count()
        if active > 0 and not force:
            return {
                "checkpoint_id": checkpoint_record["id"],
                "checkpoint_name": checkpoint_record["name"],
                "restored": False,
                "blocked_reason": (
                    f"{active} active session(s) would be terminated by restore. "
                    "Re-run with force=True to override."
                ),
                "active_sessions": active,
            }

        payload = self._filter_checkpoint_payload(checkpoint_record["payload"], focus_project_id) or {}
        self.session_manager.reconcile(0)

        restored_project_payloads: list[dict[str, object]] = []
        for item in payload.get("projects", []):
            project = ProjectRecord(**item)
            self.db.upsert_project(project)
            restored_project_payloads.append(project.to_dict())

        restored_runner_payloads: list[dict[str, object]] = []
        for item in payload.get("runners", []):
            runner = RunnerRecord(**item)
            runner.current_task_id = None
            runner.status = "AVAILABLE" if runner.available else "OFFLINE"
            self.db.upsert_runner(runner)
            restored_runner_payloads.append(runner.to_dict())

        restored_task_payloads: list[dict[str, object]] = []
        for item in payload.get("tasks", []):
            task = TaskRecord(**item)
            if task.status in {"ASSIGNED", "RUNNING", "VERIFYING", "NEEDS_INTERVENTION"}:
                task.status = "PAUSED"
                task.last_error = (
                    f"Restored from checkpoint {checkpoint_record['id']} ({checkpoint_record['created_at']})"
                )
            if not task.trace_id:
                task.trace_id = task.task_id
            self.db.upsert_task(task)
            restored_task_payloads.append(task.to_dict())

        restored_insight_payloads: list[dict[str, object]] = []
        for item in payload.get("insights", []):
            insight = InsightRecord(**item)
            self.db.add_insight(insight)
            restored_insight_payloads.append(insight.to_dict())

        restored_payload = dict(payload)
        restored_payload["projects"] = restored_project_payloads
        restored_payload["runners"] = restored_runner_payloads
        restored_payload["tasks"] = restored_task_payloads
        restored_payload["insights"] = restored_insight_payloads
        restored_checkpoint_id = self.memory_store.write_checkpoint("main", restored_payload)
        return {
            "checkpoint_id": checkpoint_record["id"],
            "checkpoint_name": checkpoint_record["name"],
            "created_at": checkpoint_record["created_at"],
            "restored": True,
            "restored_counts": {
                "projects": len(restored_project_payloads),
                "runners": len(restored_runner_payloads),
                "tasks": len(restored_task_payloads),
                "insights": len(restored_insight_payloads),
            },
            "restored_checkpoint_id": restored_checkpoint_id,
        }

    def replay_checkpoint(
        self,
        checkpoint_id: int | None = None,
        checkpoint_name: str = "main",
        focus_project_id: str | None = None,
    ) -> dict[str, object]:
        checkpoint_record = self._resolve_checkpoint_record(checkpoint_id, checkpoint_name)
        if checkpoint_record is None:
            return {
                "checkpoint_id": checkpoint_id,
                "checkpoint_name": checkpoint_name,
                "created_at": None,
                "payload": None,
            }
        return {
            "checkpoint_id": checkpoint_record["id"],
            "checkpoint_name": checkpoint_record["name"],
            "created_at": checkpoint_record["created_at"],
            "payload": self._filter_checkpoint_payload(checkpoint_record["payload"], focus_project_id),
        }

    def _resolve_checkpoint_record(
        self,
        checkpoint_id: int | None,
        checkpoint_name: str,
    ) -> dict[str, object] | None:
        if checkpoint_id is not None:
            return self.db.checkpoint_by_id(checkpoint_id)
        return next(iter(self.db.list_checkpoints(name=checkpoint_name, limit=1)), None)

    def show_state(self, focus_project_id: str | None = None) -> dict[str, object]:
        projects = self.db.list_projects()
        tasks = self.db.list_tasks()
        insights = self.db.list_insights()
        checkpoint = self.db.latest_checkpoint("main")
        if focus_project_id:
            projects = [project for project in projects if project.project_id == focus_project_id]
            tasks = [task for task in tasks if task.project_id == focus_project_id]
            insights = [insight for insight in insights if insight.scope == focus_project_id]
        checkpoint = self._filter_checkpoint_payload(checkpoint, focus_project_id)
        return {
            "projects": [project.to_dict() for project in projects],
            "runners": [runner.to_dict() for runner in self.db.list_runners()],
            "tasks": [task.to_dict() for task in tasks],
            "insights": [insight.to_dict() for insight in insights],
            "checkpoint": checkpoint,
        }

    @staticmethod
    def _filter_checkpoint_payload(
        checkpoint: dict[str, object] | None,
        focus_project_id: str | None,
    ) -> dict[str, object] | None:
        if checkpoint is None or not focus_project_id:
            return checkpoint
        filtered = dict(checkpoint)
        focus_task_ids: set[str] = set()
        checkpoint_projects = filtered.get("projects")
        if isinstance(checkpoint_projects, list):
            filtered["projects"] = [
                project for project in checkpoint_projects if project.get("project_id") == focus_project_id
            ]
        checkpoint_tasks = filtered.get("tasks")
        if isinstance(checkpoint_tasks, list):
            checkpoint_tasks = [
                task for task in checkpoint_tasks if task.get("project_id") == focus_project_id
            ]
            filtered["tasks"] = checkpoint_tasks
            focus_task_ids.update(
                task["task_id"]
                for task in checkpoint_tasks
                if isinstance(task, dict) and isinstance(task.get("task_id"), str)
            )
        checkpoint_insights = filtered.get("insights")
        if isinstance(checkpoint_insights, list):
            filtered["insights"] = [
                insight for insight in checkpoint_insights if insight.get("scope") == focus_project_id
            ]
        checkpoint_evidence = filtered.get("evidence")
        if isinstance(checkpoint_evidence, list):
            filtered["evidence"] = [
                item for item in checkpoint_evidence if item.get("task_id") in focus_task_ids
            ]
        checkpoint_interventions = filtered.get("interventions")
        if isinstance(checkpoint_interventions, list):
            filtered["interventions"] = [
                item for item in checkpoint_interventions if item.get("task_id") in focus_task_ids
            ]
        return filtered

    @staticmethod
    def _sanitize_prompt_value(value: str, limit: int = 200) -> str:
        """Strip prompt-injection control sequences and bound length.

        Task titles and project names flow into LLM prompts verbatim. Defence
        in depth: replace fenced-code delimiters so a hostile title cannot
        close the prompt's own code block, and cap length to avoid blowing
        past the model's context budget.
        """
        cleaned = (value or "").replace("```", "'''")
        cleaned = cleaned.replace("\r", " ").replace("\n", " ")
        if len(cleaned) > limit:
            cleaned = cleaned[: limit - 1] + "…"
        return cleaned

    def _build_worker_prompt(self, project: ProjectRecord, task: TaskRecord) -> str:
        known_commands = []
        known_commands.extend(project.build_commands)
        known_commands.extend(project.test_commands)
        known_commands.extend(project.browser_test_commands)
        known_commands.extend(project.perf_commands)
        guidance = "\n".join(f"- {line}" for line in project.guidance_summary) or "- none"
        activity_summary = "\n".join(f"- {line}" for line in project.activity_summary) or "- none"
        math_signals = ", ".join(project.advanced_math_signals) if project.advanced_math_signals else "none"
        math_rigor = (
            f"- rigor: {project.advanced_math_rigor}\n"
            f"- score: {project.advanced_math_score}\n"
            f"- signals: {math_signals}"
        )
        analysis_focus = ", ".join(project.analysis_focus_areas) if project.analysis_focus_areas else "none"
        analysis_risks = ", ".join(project.analysis_risk_factors[:4]) if project.analysis_risk_factors else "none"
        analysis_profile = (
            f"- focus: {analysis_focus}\n"
            f"- risk factors: {analysis_risks}"
        )
        verification = "\n".join(f"- {item}" for item in task.required_verification)
        safe_project_name = self._sanitize_prompt_value(project.name)
        safe_task_title = self._sanitize_prompt_value(task.title)
        if task.task_type == "verification":
            verification_plan = self.verifier.planner.plan(task, project)
            preferred_commands: list[str] = []
            for commands in verification_plan.values():
                preferred_commands.extend(commands)
            preferred_commands = list(dict.fromkeys(preferred_commands))
            primary_command = preferred_commands[0] if preferred_commands else "none discovered"
            fallback_command = preferred_commands[1] if len(preferred_commands) > 1 else "none"
            return (
                f"PROJECT:\n{safe_project_name} ({project.root_path})\n\n"
                f"TASK:\n{safe_task_title}\n\n"
                "MODE:\n"
                "- verification only\n"
                "- follow the phases below strictly\n\n"
                "PHASE 1 — QUICK RESEARCH:\n"
                "- check if the primary command exists and is runnable\n"
                "- if the project has CLAUDE.md or README.md, scan for test instructions\n"
                "- note any version or environment concerns\n\n"
                "PHASE 2 — EXECUTE:\n"
                f"- run the primary command exactly: {primary_command}\n"
                f"- if it fails, try fallback: {fallback_command}\n"
                "- print the full command output\n\n"
                "PHASE 3 — REFLECT:\n"
                "- print: RESULT: PASS or FAIL\n"
                "- print: EVIDENCE: the key output line proving pass/fail\n"
                "- print: UNCERTAIN: anything not fully confirmed\n\n"
                f"KNOWN COMMANDS:\n{chr(10).join(f'- {command}' for command in known_commands) or '- none discovered'}\n\n"
                f"RECENT ACTIVITY SIGNALS:\n{activity_summary}\n\n"
                f"STATISTICAL RIGOR:\n{math_rigor}\n\n"
                f"ANALYSIS PROFILE:\n{analysis_profile}\n\n"
                "CONSTRAINTS:\n"
                "- do not skip the research phase\n"
                "- do not claim success without terminal-visible evidence\n"
                "- if uncertain, say exactly what is uncertain\n\n"
                f"REQUIRED VERIFICATION:\n{verification}\n"
            )
        project_memories = self.memory_store.recall_for_project(project.project_id, limit=3)
        heuristic_memories = self.memory_store.recall_heuristics(task.task_type, limit=2)
        prior_learnings_lines: list[str] = []
        for mem in project_memories:
            prior_learnings_lines.append(f"- [{mem.memory_type}] {mem.title}: {mem.content[:120]}")
        for mem in heuristic_memories:
            prior_learnings_lines.append(f"- [heuristic] {mem.title}: {mem.content[:120]}")
        prior_learnings = "\n".join(prior_learnings_lines) if prior_learnings_lines else "- none"

        return self.worker_prompt_template.format(
            project_name=safe_project_name,
            project_path=project.root_path,
            task_title=safe_task_title,
            known_commands="\n".join(f"- {command}" for command in known_commands) or "- none discovered",
            guidance=guidance,
            activity_summary=activity_summary,
            math_rigor=math_rigor,
            analysis_profile=analysis_profile,
            prior_learnings=prior_learnings,
            required_verification=verification,
        )

    def _decide_interventions(
        self,
        evidence_items: list,
        policy_violations_by_task: dict[str, list] | None = None,
    ) -> list[dict[str, str]]:
        actions: list[dict[str, str]] = []
        for evidence in evidence_items:
            # PolicyGuard: check terminal output for dangerous commands
            violations = policy_violations_by_task.get(evidence.task_id, []) if policy_violations_by_task else []
            if evidence.output_excerpt and not policy_violations_by_task:
                violations = self.policy_guard.evaluate(evidence.output_excerpt)
            if violations:
                actions.extend(
                    self.policy_guard.to_interventions(violations, evidence.task_id)
                )

            if evidence.loop_detected:
                actions.append(
                    {
                        "task_id": evidence.task_id,
                        "action": "send_message",
                        "message": "Stop retrying. Summarize the current state in 8 lines and isolate the failing step.",
                    }
                )
            elif evidence.proof_gap and not evidence.exited:
                actions.append(
                    {
                        "task_id": evidence.task_id,
                        "action": "send_message",
                        "message": self.critique_prompt,
                    }
                )
            elif "session idle beyond limit" in evidence.risks:
                actions.append(
                    {
                        "task_id": evidence.task_id,
                        "action": "pause",
                        "message": "Checkpoint and pause.",
                    }
                )
        return actions

    def _blocking_policy_message(self, line: str) -> str | None:
        violation = next(
            (violation for violation in self.policy_guard.evaluate([line]) if violation.severity == "block"),
            None,
        )
        if violation is None:
            return None
        return f"{violation.rule_name}: {violation.message}"

    def _apply_completion_gates(
        self,
        task: TaskRecord,
        project: ProjectRecord,
        verification_result: VerificationResult,
        transcript_lines: list[str] | None = None,
        include_judge: bool = True,
    ) -> VerificationResult:
        if not verification_result.success:
            return verification_result

        required_checks = list(verification_result.required_checks)
        completed_checks = list(verification_result.completed_checks)
        skipped_checks = list(verification_result.skipped_checks)
        details = list(verification_result.details)

        if task.verify_command:
            required_checks = self._append_unique_check(required_checks, "verify_command")
            verify_passed, verify_detail = self._run_verify_command_with_detail(task, project)
            details.append(verify_detail)
            if verify_passed:
                completed_checks = self._append_unique_check(completed_checks, "verify_command")
            else:
                skipped_checks = self._append_unique_check(skipped_checks, "verify_command")
                return VerificationResult(
                    task_id=verification_result.task_id,
                    success=False,
                    required_checks=required_checks,
                    completed_checks=completed_checks,
                    skipped_checks=skipped_checks,
                    details=details,
                    trace_id=verification_result.trace_id,
                )

        if include_judge and self.llm_judge is not None:
            judge_verdict = self.llm_judge.judge(
                task=task,
                project=project,
                verification_result=verification_result,
                transcript_lines=transcript_lines,
            )
            judge_available = "judge_error" not in judge_verdict.concerns
            if judge_available:
                required_checks = self._append_unique_check(required_checks, "semantic_requirements")
                if not judge_verdict.passed and judge_verdict.confidence >= 0.7:
                    skipped_checks = self._append_unique_check(skipped_checks, "semantic_requirements")
                    details.append(f"judge: {judge_verdict.reasoning[:200]}")
                    return VerificationResult(
                        task_id=verification_result.task_id,
                        success=False,
                        required_checks=required_checks,
                        completed_checks=completed_checks,
                        skipped_checks=skipped_checks,
                        details=details,
                        trace_id=verification_result.trace_id,
                    )
                completed_checks = self._append_unique_check(completed_checks, "semantic_requirements")
                details.append(f"judge: pass (conf={judge_verdict.confidence:.2f})")

        return VerificationResult(
            task_id=verification_result.task_id,
            success=True,
            required_checks=required_checks,
            completed_checks=completed_checks,
            skipped_checks=skipped_checks,
            details=details,
            trace_id=verification_result.trace_id,
        )

    def _build_llm_judge(self) -> LLMJudge | None:
        if not self._judge_enabled():
            return None
        return LLMJudge(backend=GeminiBackend())

    def _judge_enabled(self) -> bool:
        raw = os.environ.get("OVERMIND_ENABLE_LLM_JUDGE")
        if raw is None:
            raw = self.config.policies.limits.get("enable_llm_judge", False)
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _append_unique_check(checks: list[str], check: str) -> list[str]:
        if check in checks:
            return checks
        return [*checks, check]

    def _run_verify_command(self, task: TaskRecord, project: ProjectRecord) -> bool:
        """Run the task's verify_command. Returns True if passed."""
        passed, _detail = self._run_verify_command_with_detail(task, project)
        return passed

    def _run_verify_command_with_detail(self, task: TaskRecord, project: ProjectRecord) -> tuple[bool, str]:
        if not task.verify_command:
            return True, "verify_command: not configured"
        command = task.verify_command
        valid, detail = validate_command_prefix_with_detail(command, cwd=project.root_path)
        if not valid:
            normalized_detail = detail or f"blocked command prefix not allowlisted command={command}"
            if normalized_detail.startswith("Blocked: command prefix not allowlisted"):
                normalized_detail = normalized_detail.replace(
                    "Blocked: command prefix not allowlisted",
                    "blocked command prefix not allowlisted",
                    1,
                )
            elif normalized_detail:
                normalized_detail = normalized_detail[0].lower() + normalized_detail[1:]
            return False, f"verify_command: {normalized_detail}"
        blocking_violation = next(
            (violation for violation in self.policy_guard.evaluate([command]) if violation.severity == "block"),
            None,
        )
        if blocking_violation is not None:
            return False, (
                "verify_command: blocked by policy "
                f"{blocking_violation.rule_name}: {blocking_violation.message}"
            )
        timeout = int(self.config.policies.limits.get("verify_command_timeout", 300))
        try:
            proc = subprocess.Popen(
                split_command(command),
                **verifier_popen_kwargs(project.root_path),
            )
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
                _ = stdout, stderr
                return proc.returncode == 0, f"verify_command: exit={proc.returncode} command={command}"
            except subprocess.TimeoutExpired:
                kill_process_tree(proc)
                try:
                    proc.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
                return False, f"verify_command: timed out after {timeout}s command={command}"
        except OSError as exc:
            return False, f"verify_command: failed to start ({exc}) command={command}"

    def dream(self, dry_run: bool = False) -> dict[str, object]:
        if dry_run:
            active = self.memory_store.list_all(status="active")
            return {
                "dry_run": True,
                "active_memories": len(active),
                "would_process": True,
            }
        return self.dream_engine.dream()

    def list_memories(
        self,
        memory_type: str | None = None,
        scope: str | None = None,
        search: str | None = None,
    ) -> dict[str, object]:
        if search:
            memories = self.memory_store.search(search, scope=scope, memory_type=memory_type)
        else:
            memories = self.memory_store.list_all()
            if memory_type:
                memories = [m for m in memories if m.memory_type == memory_type]
            if scope:
                memories = [m for m in memories if m.scope == scope]
        return {
            "count": len(memories),
            "memories": [m.to_dict() for m in memories],
            "stats": self.memory_store.stats(),
        }

    def forget_memory(self, memory_id: str) -> dict[str, str]:
        self.memory_store.forget(memory_id)
        return {"forgotten": memory_id}

    def _recover_abandoned_tasks(self) -> None:
        for task in self.db.list_tasks():
            if task.status in {"ASSIGNED", "RUNNING", "VERIFYING"}:
                self.task_queue.transition(
                    task.task_id,
                    "BLOCKED",
                    last_error="Recovered after supervisor restart",
                )
