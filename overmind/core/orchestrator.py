from __future__ import annotations

import time
from pathlib import Path

from overmind.config import AppConfig
from overmind.core.health_manager import HealthManager
from overmind.core.policy_engine import PolicyEngine
from overmind.core.scheduler import Scheduler
from overmind.discovery.indexer import ProjectIndexer
from overmind.discovery.portfolio_audit import PortfolioAuditor
from overmind.memory.dream_engine import DreamEngine
from overmind.memory.extractor import MemoryExtractor
from overmind.memory.insights import InsightEngine
from overmind.memory.store import MemoryStore
from overmind.parsing.terminal_parser import TerminalParser
from overmind.runners.protocols import RunnerProtocol
from overmind.runners.runner_registry import RunnerRegistry
from overmind.sessions.session_manager import SessionManager
from overmind.storage.db import StateDatabase
from overmind.storage.models import ProjectRecord, TaskRecord
from overmind.tasks.prioritizer import Prioritizer
from overmind.tasks.task_generator import TaskGenerator
from overmind.tasks.task_models import build_baseline_task
from overmind.tasks.task_queue import TaskQueue
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
        self.scheduler = Scheduler(config.policies)
        self.task_generator = TaskGenerator()
        self.prioritizer = Prioritizer()
        self.session_manager = SessionManager(config.data_dir / "transcripts")
        self.parser = TerminalParser(
            summary_trigger_lines=int(config.policies.limits.get("summary_trigger_output_lines", 400)),
            idle_timeout_min=int(config.policies.limits.get("idle_timeout_min", 10)),
        )
        self.verifier = VerificationEngine(config.data_dir / "artifacts")
        self.memory_store = MemoryStore(
            db=self.db,
            checkpoints_dir=config.data_dir / "checkpoints",
            logs_dir=config.data_dir / "logs",
        )
        self.insight_engine = InsightEngine()
        self.memory_extractor = MemoryExtractor(self.db)
        self.dream_engine = DreamEngine(self.db)
        self.tick_count = 0
        self.worker_prompt_template = (Path(__file__).resolve().parents[1] / "prompts" / "worker_prompt.txt").read_text(
            encoding="utf-8"
        )
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

    def run_once(self, focus_project_id: str | None = None, settle_seconds: float = 0.75) -> dict[str, object]:
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
        interventions = self._decide_interventions(evidence_items)
        self.session_manager.apply_interventions(interventions)

        verification_results = []
        for evidence in evidence_items:
            task = self.db.get_task(evidence.task_id)
            if not task:
                continue
            observation = observation_map.get(evidence.task_id)
            runtime = observation.runtime_seconds if observation else 0.0
            output_lines = observation.lines if observation else []

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
                continue

            if evidence.exited and evidence.exit_code == 0:
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
                verification_results.append(result)
                if result.success:
                    self.task_queue.transition(
                        evidence.task_id,
                        "COMPLETED",
                        verification_summary=result.details,
                    )
                else:
                    self.task_queue.transition(
                        evidence.task_id,
                        "FAILED",
                        last_error="; ".join(result.details + result.skipped_checks),
                    )
                self.runner_registry.update_outcome(
                    evidence.runner_id,
                    success=result.success,
                    latency_sec=runtime,
                    output_lines=output_lines,
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
        self.memory_store.write_checkpoint("main", checkpoint_payload)

        active_memory_count = len(self.memory_store.list_all(status="active"))
        if self.dream_engine.should_dream(self.tick_count, active_memory_count):
            self.dream_engine.dream()
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
        }

    def run_loop(
        self,
        iterations: int | None = None,
        sleep_seconds: float = 5.0,
        focus_project_id: str | None = None,
    ) -> dict[str, object]:
        history: list[dict[str, object]] = []
        iteration = 0
        while iterations is None or iteration < iterations:
            history.append(self.run_once(focus_project_id=focus_project_id))
            iteration += 1
            if iterations is not None and iteration >= iterations:
                break
            time.sleep(sleep_seconds)
        return {"iterations": history}

    def show_state(self) -> dict[str, object]:
        return {
            "projects": [project.to_dict() for project in self.db.list_projects()],
            "runners": [runner.to_dict() for runner in self.db.list_runners()],
            "tasks": [task.to_dict() for task in self.db.list_tasks()],
            "insights": [insight.to_dict() for insight in self.db.list_insights()],
            "checkpoint": self.db.latest_checkpoint("main"),
        }

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
        verification = "\n".join(f"- {item}" for item in task.required_verification)
        if task.task_type == "verification":
            verification_plan = self.verifier.planner.plan(task, project)
            preferred_commands: list[str] = []
            for commands in verification_plan.values():
                preferred_commands.extend(commands)
            preferred_commands = list(dict.fromkeys(preferred_commands))
            primary_command = preferred_commands[0] if preferred_commands else "none discovered"
            fallback_command = preferred_commands[1] if len(preferred_commands) > 1 else "none"
            return (
                f"PROJECT:\n{project.name} ({project.root_path})\n\n"
                f"TASK:\n{task.title}\n\n"
                "MODE:\n"
                "- verification only\n"
                "- do not inspect CLAUDE.md, README.md, or source files unless the primary command fails\n"
                "- do not print file contents\n"
                "- run the primary command exactly as written, then stop\n\n"
                f"PRIMARY COMMAND:\n- {primary_command}\n\n"
                f"FALLBACK COMMAND:\n- {fallback_command}\n\n"
                f"KNOWN COMMANDS:\n{chr(10).join(f'- {command}' for command in known_commands) or '- none discovered'}\n\n"
                f"RECENT ACTIVITY SIGNALS:\n{activity_summary}\n\n"
                f"STATISTICAL RIGOR:\n{math_rigor}\n\n"
                "OUTPUT:\n"
                "- print the command you ran\n"
                "- print pass/fail evidence only\n"
                "- if the primary command fails, print the failure and stop\n\n"
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
            project_name=project.name,
            project_path=project.root_path,
            task_title=task.title,
            known_commands="\n".join(f"- {command}" for command in known_commands) or "- none discovered",
            guidance=guidance,
            activity_summary=activity_summary,
            math_rigor=math_rigor,
            prior_learnings=prior_learnings,
            required_verification=verification,
        )

    def _decide_interventions(self, evidence_items: list) -> list[dict[str, str]]:
        actions: list[dict[str, str]] = []
        for evidence in evidence_items:
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
                        "message": "Run minimum meaningful verification and print terminal-visible proof.",
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
