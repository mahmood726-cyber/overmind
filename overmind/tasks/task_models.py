from __future__ import annotations

import uuid

from overmind.storage.models import ProjectRecord, TaskRecord


def build_baseline_task(project: ProjectRecord) -> TaskRecord:
    required_verification = list(project.recommended_verification)
    if not required_verification:
        required_verification = ["build"]
        if project.test_commands:
            required_verification.append("relevant_tests")
        if project.browser_test_commands:
            required_verification.append("targeted_browser_test")
        if project.has_numeric_logic or project.has_validation_history:
            required_verification.append("numeric_regression")
        if project.has_advanced_math and project.test_commands:
            required_verification.extend(["deterministic_fixture_tests", "edge_case_tests", "output_comparison"])
        if project.has_advanced_math and project.advanced_math_score >= 6 and project.test_commands:
            required_verification.extend(["sensitivity_checks", "stochastic_stability"])
        if (
            project.has_advanced_math
            and project.test_commands
            and any(signal in {"diagnostic_accuracy", "calibration_validation"} for signal in project.advanced_math_signals)
        ):
            required_verification.append("calibration_checks")
        if project.has_advanced_math or project.has_oracle_benchmarks or project.has_drift_history:
            required_verification.append("regression_checks")
        if project.perf_commands and (project.has_oracle_benchmarks or project.has_drift_history):
            required_verification.append("before_after_benchmark")

    return TaskRecord(
        task_id=f"baseline_{uuid.uuid4().hex[:8]}",
        project_id=project.project_id,
        title=f"Baseline verification for {project.name}",
        task_type="verification",
        source="project_index",
        priority=0.6,
        risk=project.risk_profile if project.risk_profile != "medium" else ("medium" if not project.has_numeric_logic else "medium_high"),
        expected_runtime_min=10 + min(project.advanced_math_score, 10),
        expected_context_cost="medium" if project.advanced_math_score >= 6 else "low",
        required_verification=list(dict.fromkeys(required_verification)),
    )
