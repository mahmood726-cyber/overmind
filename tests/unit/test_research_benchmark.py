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


def test_live_corpus_lifts_search_corpus_to_first_class(tmp_path, monkeypatch):
    """With a (stubbed) live provider, the corpus step runs against a non-offline
    index and search_corpus reaches 3/3 — the only honestly-capped dimension."""
    from overmind.evidence.corpus import McpCorpusProvider
    import overmind.evidence.corpus as corpus_mod

    def fake_live():
        def fetch(query, limit):
            return [{"pmid": str(i), "title": f"SGLT2 inhibitor heart failure trial {i}",
                     "source": "pubmed", "abstract": "randomized controlled trial"} for i in range(8)]
        return McpCorpusProvider(fetch=fetch, name="pubmed-eutils")

    monkeypatch.setattr(corpus_mod, "live_pubmed_provider", fake_live)

    projects = [
        ProjectRecord(project_id=f"e{i}", name=f"E{i}", root_path=str(tmp_path / f"e{i}"),
                      project_type="python_tool", has_advanced_math=True,
                      advanced_math_signals=["meta_analysis"], analysis_focus_areas=["evidence synthesis"],
                      has_validation_history=True, risk_profile="high")
        for i in range(12)
    ]
    report = ResearchBenchmark(tmp_path / "artifacts").run(
        projects, runners=[{"runner_id": "c", "status": "AVAILABLE", "available": True}],
        meta_verify={"verdict": "CERTIFIED"}, exercise=True, live_corpus=True)
    assert _scores(report)["search_corpus"] == 3


def test_live_corpus_zero_hits_falls_back_to_offline_floor(tmp_path, monkeypatch):
    """Regression (2026-06-04 review): a live query that SUCCEEDS with zero hits must
    not crash search_corpus below the offline floor — it falls back to offline (2)."""
    from overmind.evidence.corpus import McpCorpusProvider
    import overmind.evidence.corpus as corpus_mod

    def empty_live():
        return McpCorpusProvider(fetch=lambda q, l: [], name="pubmed-eutils")

    monkeypatch.setattr(corpus_mod, "live_pubmed_provider", empty_live)
    projects = [ProjectRecord(project_id="e", name="E", root_path=str(tmp_path / "e"),
                              project_type="python_tool", analysis_focus_areas=["evidence synthesis"])]
    report = ResearchBenchmark(tmp_path / "artifacts").run(projects, exercise=True, live_corpus=True)
    # empty live result -> offline fallback -> 2, never 0/1
    assert _scores(report)["search_corpus"] == 2


def test_live_corpus_failure_falls_back_offline(tmp_path, monkeypatch):
    """If the live provider raises (network down), the corpus step fails CLOSED to
    the offline seed — search_corpus stays at 2, never credited on a failed attempt."""
    import overmind.evidence.corpus as corpus_mod

    def broken_live():
        from overmind.evidence.corpus import McpCorpusProvider

        def fetch(query, limit):
            raise RuntimeError("network down")
        return McpCorpusProvider(fetch=fetch, name="pubmed-eutils")

    monkeypatch.setattr(corpus_mod, "live_pubmed_provider", broken_live)
    projects = [ProjectRecord(project_id="e", name="E", root_path=str(tmp_path / "e"),
                              project_type="python_tool", analysis_focus_areas=["evidence synthesis"])]
    report = ResearchBenchmark(tmp_path / "artifacts").run(projects, exercise=True, live_corpus=True)
    # offline fallback corpus artifact present -> 2, not 3, not crashed
    assert _scores(report)["search_corpus"] == 2


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
