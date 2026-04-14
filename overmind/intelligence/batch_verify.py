"""Batch verification runner.

Runs verification on a batch of projects from the priority queue.
Usage: overmind batch-verify --count 10
"""
from __future__ import annotations

from overmind.core.orchestrator import Orchestrator
from overmind.intelligence.portfolio_state import (
    build_project_identity_groups,
    build_verification_state_index,
    is_verified_identity,
    project_priority_score,
    select_representative_project,
)
from overmind.storage.models import TaskRecord


def batch_verify(
    orchestrator: Orchestrator,
    count: int = 10,
    risk_filter: str | None = None,
) -> dict[str, object]:
    """Verify the top N projects from the priority queue."""
    projects = orchestrator.db.list_projects()
    memories = orchestrator.db.list_memories(limit=10000)
    verification_state = build_verification_state_index(
        projects,
        memories,
        orchestrator.config.data_dir / "artifacts",
    )
    groups = build_project_identity_groups(projects)

    candidates = []
    for identity, group in groups.items():
        project = select_representative_project(group)
        if is_verified_identity(identity, verification_state):
            continue
        if not project.test_commands:
            continue
        if risk_filter and project.risk_profile != risk_filter:
            continue
        candidates.append((project_priority_score(project), project))

    candidates.sort(key=lambda x: x[0], reverse=True)
    to_verify = [p for _, p in candidates[:count]]

    results = []
    tick = 100  # batch ticks start at 100

    for project in to_verify:
        task = TaskRecord(
            task_id=f"batch_{project.project_id[:12]}",
            project_id=project.project_id,
            title=f"Batch verification for {project.name}",
            task_type="verification",
            source="batch_verify",
            priority=1.0,
            risk=project.risk_profile,
            expected_runtime_min=5,
            expected_context_cost="medium",
            required_verification=["relevant_tests"],
            verify_command=project.test_commands[0] if project.test_commands else None,
        )

        try:
            result = orchestrator.verifier.run(task, project)
            final_result = orchestrator._apply_completion_gates(
                task=task,
                project=project,
                verification_result=result,
                include_judge=False,
            )
            status = "PASS" if final_result.success else "FAIL"

            # Extract memories
            orchestrator.memory_extractor.extract(
                evidence_items=[],
                verification_results=[final_result],
                project_ids={task.task_id: project.project_id},
                runner_ids={},
                tick=tick,
            )

            # Audit loop
            orchestrator.audit_loop.evaluate(project.project_id, final_result, tick=tick)

            vc_status = "N/A"
            if task.verify_command:
                verify_details = [
                    detail for detail in final_result.details if detail.startswith("verify_command:")
                ]
                if verify_details:
                    vc_status = "PASS" if any("exit=0" in detail for detail in verify_details) else "FAIL"

            details = "; ".join(final_result.details[:2])
        except Exception as exc:
            status = "ERROR"
            vc_status = "N/A"
            details = str(exc)[:100]

        results.append({
            "name": project.name,
            "project_id": project.project_id,
            "risk": project.risk_profile,
            "math_score": project.advanced_math_score,
            "status": status,
            "verify_command": vc_status,
            "details": details,
        })
        tick += 1

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")

    return {
        "verified": len(results),
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "results": results,
    }
