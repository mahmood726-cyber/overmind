from __future__ import annotations

import json

from overmind.intelligence.research_benchmark import ResearchBenchmark
from overmind.storage.models import ProjectRecord


def test_research_benchmark_scores_current_system_and_writes_artifacts(tmp_path):
    projects = [
        ProjectRecord(
            project_id="living-meta",
            name="Living Meta Evidence Synthesizer",
            root_path=str(tmp_path / "living-meta"),
            project_type="python_tool",
            stack=["python", "r"],
            has_advanced_math=True,
            advanced_math_signals=["meta_analysis", "network meta-analysis"],
            analysis_focus_areas=["evidence synthesis"],
            has_oracle_benchmarks=True,
            has_validation_history=True,
            test_commands=["python -m pytest"],
            risk_profile="high",
        ),
        ProjectRecord(
            project_id="dashboard",
            name="Dashboard",
            root_path=str(tmp_path / "dashboard"),
            project_type="browser_app",
            stack=["html"],
            risk_profile="medium",
        ),
    ]
    runners = [{"runner_id": "codex", "status": "AVAILABLE", "available": True}]
    benchmark = ResearchBenchmark(tmp_path / "artifacts")

    report = benchmark.run(
        projects,
        runners=runners,
        meta_verify={"verdict": "CERTIFIED", "passed": True},
    )

    assert report["benchmark_type"] == "capability_evidence_benchmark"
    assert report["portfolio_summary"]["evidence_synthesis_projects"] == 1
    assert report["portfolio_summary"]["advanced_math_projects"] == 1
    assert report["current_system_score_percent"] > 0
    assert any(row["name"] == "Elicit" for row in report["systems"])
    assert any(item["dimension"] == "statistical_verification" for item in report["strengths"])
    assert any(item["dimension"] == "search_corpus" for item in report["gaps"])

    json_path = tmp_path / "artifacts" / "research_benchmark.json"
    md_path = tmp_path / "artifacts" / "research_benchmark.md"
    assert json_path.exists()
    assert md_path.exists()
    persisted = json.loads(json_path.read_text(encoding="utf-8"))
    assert persisted["current_system_rank"] == report["current_system_rank"]
