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


def _scores(report):
    current = next(r for r in report["systems"] if r["name"].startswith("Overmind"))
    return current["scores"]


def test_evidence_gated_scores_rise_only_after_subsystems_run(tmp_path):
    """With exercise=True the benchmark runs the real (offline) evidence
    subsystems and the four gap dimensions rise above their heuristic floors."""
    projects = [
        ProjectRecord(
            project_id=f"evid-{i}", name=f"Living Meta {i}", root_path=str(tmp_path / f"e{i}"),
            project_type="python_tool", has_advanced_math=True,
            advanced_math_signals=["meta_analysis"], analysis_focus_areas=["evidence synthesis"],
            has_validation_history=True, risk_profile="high",
        )
        for i in range(12)  # >=10 so review_workflow floor is 2
    ]
    benchmark = ResearchBenchmark(tmp_path / "artifacts")
    report = benchmark.run(projects, runners=[{"runner_id": "codex", "status": "AVAILABLE", "available": True}],
                           meta_verify={"verdict": "CERTIFIED"}, exercise=True)
    scores = _scores(report)
    # exercised on the bundled real corpus + demo fixture:
    assert scores["search_corpus"] == 2          # offline BM25 over a real corpus
    assert scores["screening_extraction"] == 3   # screening + extraction both produced
    assert scores["citation_grounding"] == 3     # claims resolved to corpus records
    assert scores["review_workflow"] == 3        # PRISMA flow artifact present
    assert "corpus_search" in report["evidence_artifacts_used"]
    assert "prisma" in report["evidence_artifacts_used"]


def test_fail_closed_no_artifacts_keeps_floor(tmp_path):
    """exercise=False with an empty artifacts dir => scores stay at the heuristic
    floor; search_corpus is NOT credited without an artifact."""
    projects = [ProjectRecord(project_id="e", name="E", root_path=str(tmp_path / "e"),
                              project_type="python_tool", analysis_focus_areas=["evidence synthesis"])]
    benchmark = ResearchBenchmark(tmp_path / "artifacts")
    report = benchmark.run(projects, exercise=False)
    scores = _scores(report)
    assert scores["search_corpus"] == 0          # no artifact => no credit
    assert report["evidence_artifacts_used"] == []
