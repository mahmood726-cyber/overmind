"""Manual full-system E2E harness for Overmind.

This file stays under ``tests/`` so it is easy to discover, but it must not
run real orchestration work during normal ``pytest`` collection.
"""

from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.skipif(
    os.environ.get("OVERMIND_RUN_E2E") != "1",
    reason="manual real-project e2e harness; set OVERMIND_RUN_E2E=1 to run",
)


def run_full_e2e() -> dict[str, object]:
    from pathlib import Path

    from overmind.activation.context_injector import ContextInjector
    from overmind.activation.session_tracker import SessionTracker
    from overmind.config import AppConfig
    from overmind.core.orchestrator import Orchestrator
    from overmind.intelligence.daily_report import DailyReport
    from overmind.intelligence.session_miner import SessionMiner
    from overmind.isolation.worktree_manager import WorktreeManager
    from overmind.parsing.loop_detector import LoopDetector
    from overmind.review.finding import compute_consensus, parse_review_output
    from overmind.review.multi_persona import MultiPersonaReviewer
    from overmind.runners.protocols import INTERACTIVE, ONE_SHOT, PIPE
    from overmind.storage.models import TaskRecord
    from overmind.tasks.task_queue import TaskQueue

    passed = 0
    failed = 0
    errors: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  [PASS] {name}")
            return
        failed += 1
        errors.append(f"{name}: {detail}")
        print(f"  [FAIL] {name} -- {detail}")

    config = AppConfig.from_directory()
    orch = Orchestrator(config)
    injector = ContextInjector(orch.db)
    tracker = SessionTracker(orch.db)
    reviewer = MultiPersonaReviewer(orch.db)

    try:
        print("=" * 60)
        print("OVERMIND COMPREHENSIVE E2E TEST")
        print("=" * 60)

        print("\n1. PROJECT SCANNING")
        projects = orch.db.list_projects()
        check("Scan found projects", len(projects) > 300, f"found {len(projects)}")
        high_risk = [project for project in projects if project.risk_profile == "high"]
        check("High-risk detected", len(high_risk) > 50, f"{len(high_risk)}")
        math_projects = [project for project in projects if project.has_advanced_math]
        check("Math projects detected", len(math_projects) > 100, f"{len(math_projects)}")

        print("\n2. SESSION TRACKING")
        tracker.cleanup_stale()
        session_a = tracker.register("claude", "C:\\Models\\BayesianMA")
        session_b = tracker.register("codex", "C:\\Models\\MetaGuard")
        check("Sessions registered", len(tracker.active_sessions()) >= 2)
        check("Project paths tracked", len(tracker.active_project_paths()) >= 2)
        tracker.close_session(session_a)
        tracker.close_session(session_b)
        check(
            "Sessions closed",
            all(
                session["session_id"] not in (session_a, session_b)
                for session in tracker.active_sessions()
            ),
        )

        print("\n3. CONTEXT INJECTION")
        context = injector.build_context("C:\\Models\\BayesianMA", "claude")
        check("BayesianMA context non-empty", len(context) > 50, f"{len(context)} chars")
        check("Contains OVERMIND header", "OVERMIND CONTEXT" in context)
        unknown_context = injector.build_context("C:\\nonexistent\\truly\\nothing", "claude")
        check(
            "Unknown project has no project learnings",
            "Prior Learnings for This Project" not in unknown_context,
            f"got {len(unknown_context)} chars",
        )

        print("\n4. VERIFICATION ENGINE")
        bayesian = orch.db.get_project("bayesianma-240f4a74")
        result = None
        if bayesian:
            task = TaskRecord(
                task_id="e2e-v-ba",
                project_id=bayesian.project_id,
                title="E2E verify",
                task_type="verification",
                source="e2e",
                priority=1.0,
                risk="high",
                expected_runtime_min=5,
                expected_context_cost="medium",
                required_verification=["relevant_tests"],
                verify_command=bayesian.test_commands[0] if bayesian.test_commands else None,
            )
            result = orch.verifier.run(task, bayesian)
            check("BayesianMA verification passes", result.success)
            check("Details populated", len(result.details) > 0)
            if task.verify_command:
                check("verify_command passes", orch._run_verify_command(task, bayesian))
        else:
            check("BayesianMA found", False, "not in DB")

        print("\n5. MEMORY EXTRACTION")
        if bayesian and result:
            memories = orch.memory_extractor.extract(
                evidence_items=[],
                verification_results=[result],
                project_ids={task.task_id: bayesian.project_id},
                runner_ids={},
                tick=600,
            )
            check("Memories extracted", len(memories) >= 1)

        print("\n6. AUDIT LOOP")
        if bayesian and result:
            assessment = orch.audit_loop.evaluate(bayesian.project_id, result, tick=600)
            check("Has pass_rate", "current_pass_rate" in assessment)
            check(
                "Has trend",
                assessment.get("trend") in ("baseline", "stable", "improving", "degrading"),
            )

        print("\n7. Q-LEARNING ROUTER")
        orch.q_router.record("test_runner", "test_task", True)
        orch.q_router.record("test_runner", "test_task", True)
        orch.q_router.record("test_runner", "test_task", False)
        q_value = orch.q_router.score("test_runner", "test_task")
        check("Q-value computed", 0.4 < q_value < 0.9, f"q={q_value:.3f}")
        check("Default is 0.5", orch.q_router.score("x", "y") == 0.5)

        print("\n8. LOOP DETECTION")
        detector = LoopDetector()
        check("Exact repeat", detector.detect(["same", "same", "same"]))
        check(
            "Fingerprint loop",
            detector.detect(
                [
                    "Error at 10:30:01 code 42",
                    "Error at 10:30:05 code 43",
                    "Error at 10:30:09 code 44",
                ]
            ),
        )
        check("Different not flagged", not detector.detect(["Build A", "Test A", "Build B", "Test B"]))

        print("\n9. DAG DEPENDENCIES")
        queue = TaskQueue(orch.db)
        build_task = TaskRecord(
            task_id="dag-b2",
            project_id="test",
            title="Build",
            task_type="verification",
            source="test",
            priority=0.9,
            risk="medium",
            expected_runtime_min=1,
            expected_context_cost="low",
            required_verification=["build"],
            status="QUEUED",
        )
        test_task = TaskRecord(
            task_id="dag-t2",
            project_id="test",
            title="Test",
            task_type="verification",
            source="test",
            priority=0.8,
            risk="medium",
            expected_runtime_min=1,
            expected_context_cost="low",
            required_verification=["test"],
            status="QUEUED",
            blocked_by=["dag-b2"],
        )
        queue.upsert([build_task, test_task])
        queued_ids = {queued.task_id for queued in queue.queued()}
        check("Build is queued", "dag-b2" in queued_ids)
        check("Test is blocked", "dag-t2" not in queued_ids)

        print("\n10. DRY RUN")
        dry_run = orch.run_once(dry_run=True)
        check("Returns dry_run flag", dry_run.get("dry_run") is True)
        check("Has would_dispatch", "would_dispatch" in dry_run)

        print("\n11. RUNNER PROTOCOLS")
        check("INTERACTIVE stdin open", not INTERACTIVE.close_stdin_after_prompt)
        check("ONE_SHOT closes stdin", ONE_SHOT.close_stdin_after_prompt)
        check("PIPE filters decorative", PIPE.filter_output("--------") is None)
        check("PIPE keeps content", PIPE.filter_output("tests passed") == "tests passed")
        check("PIPE wraps prompt", "concise" in PIPE.wrap_prompt("test").lower())
        check("PIPE capacity patterns", len(PIPE.capacity_error_patterns) >= 4)

        print("\n12. MULTI-PERSONA REVIEW")
        if bayesian:
            personas = reviewer.select_personas(bayesian)
            check("5 personas for high-risk math", len(personas) == 5)
            runner = reviewer.preferred_runner_for(personas[0], "claude")
            check("Cross-model dispatch", runner != "claude")

        review_a = parse_review_output("correctness", "- [P1] Missing check\nVERDICT: CONCERNS")
        review_b = parse_review_output("robustness", "- [P1] Missing check on input\nVERDICT: CONCERNS")
        consensus = compute_consensus([review_a, review_b])
        check("Consensus computed", consensus.overall_verdict in ("PASS", "CONCERNS", "BLOCK"))

        print("\n13. DREAMING")
        dream = orch.dream_engine.dream()
        check("Dream has summary", "memories_before" in dream)
        check("Dream has merges", "merges" in dream)

        print("\n14. SESSION MINING")
        miner = SessionMiner(orch.db)
        mined = miner.mine_all(max_sessions=5)
        check("Miner runs", mined["sessions_analyzed"] > 0)
        check("Finds messages", mined["total_messages"] > 0)

        print("\n15. DAILY REPORT")
        reporter = DailyReport(orch.db, config.data_dir / "artifacts")
        report = reporter.generate()
        check("Has portfolio", "portfolio" in report)
        check("Has benchmark", "benchmark" in report)
        check("Has session mining", "session_mining" in report)
        check("Has priority queue", len(report.get("priority_queue", [])) > 0)
        report_paths = reporter.write(report)
        check("Written to disk", Path(report_paths["markdown"]).exists())

        print("\n16. MEMORY HEALTH")
        stats = orch.memory_store.stats()
        check("Memories > 20", stats.get("total", 0) > 20, f"total={stats.get('total', 0)}")
        search_results = orch.memory_store.search("verification")
        check("FTS5 search works", len(search_results) > 0)

        print("\n17. WORKTREE ISOLATION")
        worktree_manager = WorktreeManager(config.data_dir / "worktrees")
        check("Non-git returns None", worktree_manager.create(Path("C:/Windows"), "test") is None)
        check("Detects concurrent", worktree_manager.needs_isolation(Path("C:/X"), {"C:\\X"}))

        print("\n18. PROMPTS")
        if bayesian:
            verification_task = TaskRecord(
                task_id="pt1",
                project_id=bayesian.project_id,
                title="Test",
                task_type="verification",
                source="test",
                priority=0.9,
                risk="high",
                expected_runtime_min=5,
                expected_context_cost="medium",
                required_verification=["relevant_tests"],
            )
            verification_prompt = orch._build_worker_prompt(bayesian, verification_task)
            check("Verification has PHASE 1", "PHASE 1" in verification_prompt)
            check("Verification has REFLECT", "REFLECT" in verification_prompt)

            focused_task = TaskRecord(
                task_id="pt2",
                project_id=bayesian.project_id,
                title="Fix bug",
                task_type="focused_fix",
                source="test",
                priority=0.9,
                risk="high",
                expected_runtime_min=5,
                expected_context_cost="medium",
                required_verification=["relevant_tests"],
            )
            worker_prompt = orch._build_worker_prompt(bayesian, focused_task)
            check("Worker has RESEARCH", "RESEARCH" in worker_prompt)
            check("Worker has PRIOR LEARNINGS", "PRIOR LEARNINGS" in worker_prompt)

        print("\n" + "=" * 60)
        print(f"RESULTS: {passed} PASSED, {failed} FAILED out of {passed + failed}")
        if errors:
            print("\nFAILURES:")
            for error in errors:
                print(f"  - {error}")
        print("=" * 60)

        return {"passed": passed, "failed": failed, "errors": errors}
    finally:
        orch.close()


def test_real_project_e2e_harness() -> None:
    result = run_full_e2e()
    assert result["failed"] == 0, "\n".join(result["errors"])


if __name__ == "__main__":
    summary = run_full_e2e()
    raise SystemExit(1 if summary["failed"] else 0)
