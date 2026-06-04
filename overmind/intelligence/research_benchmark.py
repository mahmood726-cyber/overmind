from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any

from overmind.storage.models import ProjectRecord, utc_now


SCORE_SCALE = {
    0: "no public evidence or not a core capability",
    1: "limited or adjacent capability",
    2: "strong partial capability",
    3: "first-class documented capability",
}


@dataclass(frozen=True, slots=True)
class BenchmarkDimension:
    dimension_id: str
    label: str
    weight: float
    description: str


@dataclass(frozen=True, slots=True)
class SystemProfile:
    name: str
    category: str
    source_url: str
    source_checked: str
    source_summary: str
    scores: dict[str, int]
    notes: list[str]


DIMENSIONS = [
    BenchmarkDimension(
        "search_corpus",
        "Scholarly search and corpus access",
        0.9,
        "Can the system retrieve papers from a large scholarly corpus or index?",
    ),
    BenchmarkDimension(
        "review_workflow",
        "Systematic-review workflow coverage",
        1.0,
        "Does it cover search, screening, extraction, reporting, or living-review workflow steps?",
    ),
    BenchmarkDimension(
        "screening_extraction",
        "Screening and data-extraction automation",
        1.1,
        "Does it automate study screening, coding, extraction, or related review labor?",
    ),
    BenchmarkDimension(
        "citation_grounding",
        "Evidence and citation grounding",
        1.1,
        "Are outputs tied to papers, citations, quotes, source records, or auditable evidence?",
    ),
    BenchmarkDimension(
        "statistical_verification",
        "Statistical and numerical verification",
        1.4,
        "Does it verify calculations, statistical claims, numerical baselines, or meta-analytic outputs?",
    ),
    BenchmarkDimension(
        "continuous_verification",
        "Continuous verification and orchestration",
        1.4,
        "Can it repeatedly monitor, route, verify, or gate work across projects?",
    ),
    BenchmarkDimension(
        "auditability_governance",
        "Auditability and fail-closed governance",
        1.3,
        "Does it preserve audit trails, block unsafe outputs, or enforce transparent governance?",
    ),
    BenchmarkDimension(
        "local_control",
        "Local/open control",
        0.8,
        "Can the user inspect, modify, self-host, or run the system locally?",
    ),
    BenchmarkDimension(
        "public_benchmarking",
        "Public benchmark transparency",
        1.0,
        "Does public documentation expose validation, benchmark, simulation, or test evidence?",
    ),
]


COMPARABLE_SYSTEMS = [
    SystemProfile(
        name="Elicit",
        category="AI scientific research and systematic-review assistant",
        source_url="https://elicit.com/welcome",
        source_checked="2026-06-03",
        source_summary=(
            "Public product page describes scholarly search, systematic-review screening and "
            "data extraction, sentence-level citations, and posted systematic-review validation."
        ),
        scores={
            "search_corpus": 3,
            "review_workflow": 3,
            "screening_extraction": 3,
            "citation_grounding": 3,
            "statistical_verification": 0,
            "continuous_verification": 1,
            "auditability_governance": 2,
            "local_control": 0,
            "public_benchmarking": 3,
        },
        notes=[
            "Strongest comparator for front-door literature search and systematic-review workflow.",
            "Benchmark here does not independently verify Elicit's posted accuracy claims.",
        ],
    ),
    SystemProfile(
        name="DistillerSR",
        category="Enterprise AI-enabled literature-review platform",
        source_url="https://www.distillersr.com/products/distillersr-systematic-review-software",
        source_checked="2026-06-03",
        source_summary=(
            "Public product page describes AI-enabled evidence synthesis, screening rerank, "
            "AI classifiers, smart extraction, traceability, audit logs, and PRISMA reporting."
        ),
        scores={
            "search_corpus": 2,
            "review_workflow": 3,
            "screening_extraction": 3,
            "citation_grounding": 2,
            "statistical_verification": 1,
            "continuous_verification": 2,
            "auditability_governance": 3,
            "local_control": 0,
            "public_benchmarking": 2,
        },
        notes=[
            "Strong enterprise comparator for regulated literature-review operations.",
            "Statistical verification is scored as limited because public claims focus on workflow and extraction.",
        ],
    ),
    SystemProfile(
        name="ASReview",
        category="Open-source active-learning screening tool",
        source_url="https://asreview.nl/",
        source_checked="2026-06-03",
        source_summary=(
            "Public project page describes open-source AI screening, workload reduction, "
            "simulation/performance comparison, local control, and transparent systematic reviews."
        ),
        scores={
            "search_corpus": 0,
            "review_workflow": 2,
            "screening_extraction": 3,
            "citation_grounding": 1,
            "statistical_verification": 0,
            "continuous_verification": 1,
            "auditability_governance": 2,
            "local_control": 3,
            "public_benchmarking": 2,
        },
        notes=[
            "Best open-source comparator for active-learning title/abstract screening.",
            "Not scored as a full evidence-synthesis verifier because its core workflow is screening.",
        ],
    ),
    SystemProfile(
        name="Consensus",
        category="AI academic search and synthesis engine",
        source_url="https://help.consensus.app/en/articles/9922673-how-consensus-works",
        source_checked="2026-06-03",
        source_summary=(
            "Help center describes a large peer-reviewed paper database, hybrid semantic/BM25 "
            "search, paper-grounded answers, Pro Analysis, Ask Paper, and Consensus Meter."
        ),
        scores={
            "search_corpus": 3,
            "review_workflow": 1,
            "screening_extraction": 0,
            "citation_grounding": 3,
            "statistical_verification": 0,
            "continuous_verification": 1,
            "auditability_governance": 1,
            "local_control": 0,
            "public_benchmarking": 1,
        },
        notes=[
            "Strong comparator for paper-grounded question answering and synthesis.",
            "Not a dedicated systematic-review verification or numerical audit system.",
        ],
    ),
    SystemProfile(
        name="Scite",
        category="AI literature search with citation-context classification",
        source_url="https://scite.ai/",
        source_checked="2026-06-03",
        source_summary=(
            "Public page describes full-text search, Smart Citations, evidence-grounded answers, "
            "and citation contexts classified as supporting or contradicting."
        ),
        scores={
            "search_corpus": 3,
            "review_workflow": 1,
            "screening_extraction": 0,
            "citation_grounding": 3,
            "statistical_verification": 0,
            "continuous_verification": 1,
            "auditability_governance": 1,
            "local_control": 0,
            "public_benchmarking": 1,
        },
        notes=[
            "Strong comparator for citation-context and claim-support analysis.",
            "Not a systematic-review execution or meta-analysis verification engine.",
        ],
    ),
    SystemProfile(
        name="Semantic Scholar",
        category="AI scholarly search and paper-understanding platform",
        source_url="https://www.semanticscholar.org/product/tldr",
        source_checked="2026-06-03",
        source_summary=(
            "Public product page describes automatically generated paper TLDRs and API access "
            "for summaries over a large scholarly graph."
        ),
        scores={
            "search_corpus": 3,
            "review_workflow": 1,
            "screening_extraction": 0,
            "citation_grounding": 2,
            "statistical_verification": 0,
            "continuous_verification": 1,
            "auditability_governance": 1,
            "local_control": 0,
            "public_benchmarking": 2,
        },
        notes=[
            "Strong comparator for scholarly discovery infrastructure.",
            "Scored lower on review execution because it is not a dedicated review workflow tool.",
        ],
    ),
    SystemProfile(
        name="RobotReviewer",
        category="Biomedical evidence-synthesis automation research system",
        source_url="https://aclanthology.org/P17-4002/",
        source_checked="2026-06-03",
        source_summary=(
            "ACL system-demonstration paper documents RobotReviewer as a biomedical "
            "evidence-synthesis automation system."
        ),
        scores={
            "search_corpus": 0,
            "review_workflow": 2,
            "screening_extraction": 2,
            "citation_grounding": 2,
            "statistical_verification": 0,
            "continuous_verification": 0,
            "auditability_governance": 1,
            "local_control": 2,
            "public_benchmarking": 2,
        },
        notes=[
            "Closest historical comparator for risk-of-bias and evidence-synthesis automation.",
            "Scored as research-system evidence, not a currently validated commercial workflow.",
        ],
    ),
]


def _weighted_total(scores: dict[str, int]) -> float:
    total = 0.0
    for dim in DIMENSIONS:
        total += scores.get(dim.dimension_id, 0) * dim.weight
    return round(total, 2)


def _max_total() -> float:
    return round(sum(3 * dim.weight for dim in DIMENSIONS), 2)


def _score_percent(scores: dict[str, int]) -> float:
    return round(_weighted_total(scores) / _max_total() * 100, 1)


def _is_evidence_synthesis_project(project: ProjectRecord) -> bool:
    haystack = " ".join(
        project.analysis_focus_areas
        + project.analysis_risk_factors
        + project.advanced_math_signals
        + [project.name, project.project_type]
    ).lower()
    needles = (
        "evidence synthesis",
        "systematic review",
        "meta_analysis",
        "meta-analysis",
        "network meta",
        "nma",
        "living meta",
        "risk of bias",
        "trial",
    )
    return any(needle in haystack for needle in needles)


def _portfolio_summary(projects: list[ProjectRecord], runners: list[dict[str, Any]] | None) -> dict[str, Any]:
    evidence_projects = [project for project in projects if _is_evidence_synthesis_project(project)]
    testable = [
        project for project in projects
        if project.test_commands or project.browser_test_commands or project.perf_commands
    ]
    available_runners = [
        runner for runner in (runners or [])
        if runner.get("available", True) and runner.get("status") == "AVAILABLE"
    ]
    return {
        "project_count": len(projects),
        "evidence_synthesis_projects": len(evidence_projects),
        "advanced_math_projects": sum(1 for project in projects if project.has_advanced_math),
        "oracle_benchmark_projects": sum(1 for project in projects if project.has_oracle_benchmarks),
        "validation_history_projects": sum(1 for project in projects if project.has_validation_history),
        "testable_projects": len(testable),
        "high_risk_projects": sum(1 for project in projects if project.risk_profile in {"high", "medium_high"}),
        "runner_count": len(runners or []),
        "available_runner_count": len(available_runners),
    }


def _current_system_scores(
    summary: dict[str, Any],
    meta_verify: dict[str, Any] | None,
    evidence_artifacts: dict[str, Any] | None = None,
) -> tuple[dict[str, int], dict[str, str]]:
    evidence_count = summary["evidence_synthesis_projects"]
    advanced_math = summary["advanced_math_projects"]
    validation = summary["validation_history_projects"]
    oracle = summary["oracle_benchmark_projects"]
    runners = summary["available_runner_count"]
    meta_certified = bool(meta_verify and meta_verify.get("verdict") == "CERTIFIED")
    art = evidence_artifacts or {}

    # Heuristic FLOORS (portfolio-signal based, unchanged). Evidence artifacts can
    # only RAISE a score above its floor, never lower it — and only when a real,
    # non-empty artifact proves the capability actually ran. Missing artifact =>
    # floor (fail-closed). This keeps the benchmark honest: a score rises because
    # the capability was built AND exercised, not because a constant changed.
    scores = {
        "search_corpus": 0,
        "review_workflow": 2 if evidence_count >= 10 else (1 if evidence_count else 0),
        "screening_extraction": 1 if evidence_count else 0,
        "citation_grounding": 2 if validation or evidence_count else 1,
        "statistical_verification": 3 if advanced_math else 1,
        "continuous_verification": 3 if runners and meta_certified else (2 if runners else 1),
        "auditability_governance": 3 if meta_certified else 2,
        "local_control": 3,
        "public_benchmarking": 3 if (oracle and meta_certified) else (2 if oracle or meta_certified else 1),
    }
    evidence = {
        "search_corpus": "No corpus-search artifact present; run `overmind corpus-search`.",
        "review_workflow": f"{evidence_count} indexed projects carry evidence-synthesis or review-like signals.",
        "screening_extraction": (
            "No screening/extraction artifact present; run `overmind screen` / `overmind extract-validate`."
        ),
        "citation_grounding": (
            f"{validation} projects carry validation-history signals; Sentinel/TruthCert rules enforce source-backed claims."
        ),
        "statistical_verification": f"{advanced_math} indexed projects carry advanced mathematical/statistical signals.",
        "continuous_verification": (
            f"{runners} available runners; meta-verify verdict is {meta_verify.get('verdict') if meta_verify else 'not_run'}."
        ),
        "auditability_governance": "Sentinel, TruthCert, and policy guards provide fail-closed local governance.",
        "local_control": "System is local, editable Python source in the user's workspace.",
        "public_benchmarking": f"{oracle} projects carry oracle-benchmark signals; meta-verify is {meta_verify.get('verdict') if meta_verify else 'not_run'}.",
    }

    # --- evidence-gated upgrades (fail-closed) -------------------------------
    corpus = art.get("corpus_search")
    if corpus and corpus.get("corpus_size", 0) >= 1:
        size, hits = corpus.get("corpus_size", 0), corpus.get("hit_count", 0)
        scores["search_corpus"] = 2 if (size >= 5 and hits > 0) else 1
        # a LIVE/large index (not the bundled offline seed) earns first-class 3
        if corpus.get("provider_available") and corpus.get("provider") not in (None, "offline-jsonl") and hits > 0:
            scores["search_corpus"] = 3
        _live = corpus.get("provider") not in (None, "offline-jsonl")
        evidence["search_corpus"] = (
            f"corpus_search artifact: provider={corpus.get('provider')}, corpus_size={size}, "
            f"hits={hits} ({'live' if _live else 'offline'} retrieval; BM25 lexical re-rank, not semantic)."
        )

    screening = art.get("screening")
    extraction = art.get("extraction")
    if screening or extraction:
        scores["screening_extraction"] = max(scores["screening_extraction"], 2)
    if screening and extraction and extraction.get("validated_count", 0) > 0:
        scores["screening_extraction"] = 3
    if screening or extraction:
        evidence["screening_extraction"] = (
            f"screening artifact: {bool(screening)} ({screening.get('proposal_count') if screening else 0} proposals, "
            f"0 auto-included); extraction artifact: {bool(extraction)} "
            f"({extraction.get('validated_count') if extraction else 0} validated, "
            f"{extraction.get('needs_review_count') if extraction else 0} flagged)."
        )

    grounding = art.get("citation_grounding")
    if grounding and grounding.get("claim_count", 0) > 0 and grounding.get("grounding_ratio") is not None:
        scores["citation_grounding"] = max(scores["citation_grounding"], 3)
        evidence["citation_grounding"] = (
            f"citation_grounding artifact: {grounding.get('grounded_count')}/{grounding.get('claim_count')} "
            f"claims resolved to corpus records (ratio={grounding.get('grounding_ratio')}); "
            "ungrounded claims are reported, never assumed."
        )

    prisma = art.get("prisma")
    if prisma and prisma.get("identification", {}).get("records_identified", 0) > 0:
        scores["review_workflow"] = max(scores["review_workflow"], 3)
        inc = prisma.get("included", {}).get("studies_included")
        evidence["review_workflow"] = (
            f"PRISMA 2020 flow artifact present: "
            f"{prisma['identification']['records_identified']} identified -> {inc} included; "
            f"{evidence_count} indexed evidence-synthesis projects."
        )

    return scores, evidence


def _profile_to_row(profile: SystemProfile) -> dict[str, Any]:
    return {
        "name": profile.name,
        "category": profile.category,
        "source_url": profile.source_url,
        "source_checked": profile.source_checked,
        "source_summary": profile.source_summary,
        "scores": dict(profile.scores),
        "weighted_total": _weighted_total(profile.scores),
        "score_percent": _score_percent(profile.scores),
        "notes": list(profile.notes),
    }


class ResearchBenchmark:
    def __init__(self, artifacts_dir: Path) -> None:
        self.artifacts_dir = artifacts_dir
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def build_report(
        self,
        projects: list[ProjectRecord],
        runners: list[dict[str, Any]] | None = None,
        meta_verify: dict[str, Any] | None = None,
        evidence_artifacts: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        summary = _portfolio_summary(projects, runners)
        current_scores, current_evidence = _current_system_scores(
            summary, meta_verify, evidence_artifacts
        )
        current_row = {
            "name": "Overmind + Sentinel + TruthCert",
            "category": "Local evidence-first research verification system",
            "source_url": "local workspace",
            "source_checked": "runtime",
            "source_summary": "Computed from indexed project records and optional current verifier status.",
            "scores": current_scores,
            "score_evidence": current_evidence,
            "weighted_total": _weighted_total(current_scores),
            "score_percent": _score_percent(current_scores),
            "notes": [
                "This system is strongest as a verifier/governance/orchestration layer.",
                "It is not scored as a literature search corpus unless a search backend is explicitly measured.",
            ],
        }
        systems = [current_row] + [_profile_to_row(profile) for profile in COMPARABLE_SYSTEMS]
        systems.sort(key=lambda row: (-row["weighted_total"], row["name"].lower()))
        for rank, row in enumerate(systems, start=1):
            row["rank"] = rank

        competitor_scores_by_dim = {
            dim.dimension_id: [profile.scores.get(dim.dimension_id, 0) for profile in COMPARABLE_SYSTEMS]
            for dim in DIMENSIONS
        }
        gaps = []
        strengths = []
        for dim in DIMENSIONS:
            current = current_scores.get(dim.dimension_id, 0)
            competitor_max = max(competitor_scores_by_dim[dim.dimension_id])
            competitor_median = median(competitor_scores_by_dim[dim.dimension_id])
            if competitor_max > current:
                gaps.append({
                    "dimension": dim.dimension_id,
                    "label": dim.label,
                    "current_score": current,
                    "best_comparator_score": competitor_max,
                    "gap": competitor_max - current,
                })
            if current >= competitor_max or current > competitor_median:
                strengths.append({
                    "dimension": dim.dimension_id,
                    "label": dim.label,
                    "current_score": current,
                    "competitor_median": competitor_median,
                })

        return {
            "generated_at": utc_now(),
            "benchmark_type": "capability_evidence_benchmark",
            "score_scale": SCORE_SCALE,
            "max_weighted_total": _max_total(),
            "dimensions": [asdict(dim) for dim in DIMENSIONS],
            "portfolio_summary": summary,
            "systems": systems,
            "current_system_rank": next(row["rank"] for row in systems if row["name"] == current_row["name"]),
            "current_system_score_percent": current_row["score_percent"],
            "strengths": strengths,
            "gaps": gaps,
            "interpretation": [
                "Use this as a capability and governance benchmark, not as an accuracy leaderboard.",
                "External systems are scored from public documentation and publications; they were not run on shared fixtures here.",
                "A true accuracy benchmark requires a locked task set, blinded expected answers, and the same inputs submitted to each system.",
            ],
        }

    def write_report(self, report: dict[str, Any]) -> dict[str, str]:
        json_path = self.artifacts_dir / "research_benchmark.json"
        md_path = self.artifacts_dir / "research_benchmark.md"
        json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        md_path.write_text(self._to_markdown(report), encoding="utf-8")
        return {"json": str(json_path), "markdown": str(md_path)}

    # Map of evidence artifact filename (under <artifacts>/evidence/) -> report key.
    _EVIDENCE_FILES = {
        "corpus_search.json": "corpus_search",
        "screening.json": "screening",
        "extraction.json": "extraction",
        "citation_grounding.json": "citation_grounding",
        "prisma.json": "prisma",
        "outcome_switching.json": "outcome_switching",
    }

    def read_evidence_artifacts(self) -> dict[str, Any]:
        """Read whatever evidence artifacts exist under <artifacts>/evidence/.
        Missing/unreadable files are simply absent (fail-closed: no credit)."""
        out: dict[str, Any] = {}
        ev_dir = self.artifacts_dir / "evidence"
        for fname, key in self._EVIDENCE_FILES.items():
            path = ev_dir / fname
            if not path.is_file():
                continue
            try:
                out[key] = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
        return out

    def exercise_evidence(self, live_corpus: bool = False) -> dict[str, Any]:
        """Run each evidence subsystem on the bundled (real, offline) corpus so the
        benchmark self-demonstrates the capability before scoring it. Deterministic,
        offline, no fabrication: corpus/screening/PRISMA run on the real seed records;
        extraction/grounding run on a small fixture transcribed from real PubMed
        abstracts. Returns the produced artifacts.

        ``live_corpus=True`` is OPT-IN: the corpus step queries the live NCBI
        E-utilities index (network) instead of the offline seed, which lifts the
        search_corpus capability to first-class. It fails CLOSED — any network/parse
        error falls back to the offline corpus, so the score never rises on a failed
        live attempt."""
        from pathlib import Path as _Path

        from overmind.evidence import corpus as _corpus
        from overmind.evidence.corpus import CorpusSearch, default_provider
        from overmind.evidence.extraction import extract_and_validate
        from overmind.evidence.grounding import ground_claims
        from overmind.evidence.prisma import prisma_flow
        from overmind.evidence.screening import ScreeningRun

        provider = default_provider()
        records = provider.records()
        art = self.artifacts_dir
        topic = "SGLT2 inhibitor heart failure"

        # Corpus step: offline by default; opt-in live, failing closed to offline.
        corpus_ran_live = False
        if live_corpus:
            try:
                from overmind.evidence.corpus import live_pubmed_provider
                CorpusSearch(provider=live_pubmed_provider(), artifacts_dir=art).run(topic, limit=10)
                corpus_ran_live = True
            except Exception:  # noqa: BLE001 - network/parse failure -> fall back offline
                corpus_ran_live = False
        if not corpus_ran_live:
            CorpusSearch(provider=provider, artifacts_dir=art).run(topic, limit=10)

        ScreeningRun(provider_records=records, artifacts_dir=art).run(query=topic)

        demo_path = _Path(_corpus.__file__).parent / "data" / "extraction_demo.json"
        demo = json.loads(demo_path.read_text(encoding="utf-8"))
        extract_and_validate(demo, artifacts_dir=art)

        claims = [
            {"claim_id": t["name"], "text": t["allOutcomes"][0]["title"], "source": {"pmid": t["pmid"]}}
            for t in demo
        ]
        ground_claims(claims, records, artifacts_dir=art)

        # PRISMA: screen the seed by study design from REAL article_types metadata —
        # include RCTs, exclude other designs (e.g. the meta-analysis) as wrong_design.
        prisma_records = []
        for rec in records:
            is_rct = any("Randomized Controlled Trial" in t for t in rec.article_types)
            prisma_records.append({
                "record_id": rec.record_id,
                "ta_decision": "include" if is_rct else "exclude",
                "ta_reason": None if is_rct else "wrong_design",
                "ft_decision": "include" if is_rct else None,
            })
        prisma_flow(prisma_records, artifacts_dir=art)

        return self.read_evidence_artifacts()

    def run(
        self,
        projects: list[ProjectRecord],
        runners: list[dict[str, Any]] | None = None,
        meta_verify: dict[str, Any] | None = None,
        exercise: bool = True,
        live_corpus: bool = False,
    ) -> dict[str, Any]:
        if exercise:
            try:
                evidence_artifacts = self.exercise_evidence(live_corpus=live_corpus)
            except Exception:  # noqa: BLE001 - never let demo wiring break the benchmark
                evidence_artifacts = self.read_evidence_artifacts()
        else:
            evidence_artifacts = self.read_evidence_artifacts()
        report = self.build_report(
            projects, runners=runners, meta_verify=meta_verify,
            evidence_artifacts=evidence_artifacts,
        )
        report["evidence_artifacts_used"] = sorted(evidence_artifacts.keys())
        report["artifacts"] = self.write_report(report)
        return report

    def _to_markdown(self, report: dict[str, Any]) -> str:
        lines = [
            "# Research AI Benchmark",
            "",
            f"- Generated: {report['generated_at']}",
            f"- Benchmark type: {report['benchmark_type']}",
            f"- Current system rank: {report['current_system_rank']} of {len(report['systems'])}",
            f"- Current system score: {report['current_system_score_percent']}%",
            "",
            "## Portfolio Summary",
        ]
        for key, value in report["portfolio_summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Ranking"])
        for row in report["systems"]:
            lines.append(
                f"- {row['rank']}. {row['name']}: {row['score_percent']}% "
                f"({row['weighted_total']}/{report['max_weighted_total']})"
            )
        lines.extend(["", "## Current Strengths"])
        for item in report["strengths"]:
            lines.append(f"- {item['label']}: {item['current_score']}/3")
        lines.extend(["", "## Current Gaps"])
        for item in report["gaps"]:
            lines.append(
                f"- {item['label']}: {item['current_score']}/3 vs comparator best "
                f"{item['best_comparator_score']}/3"
            )
        lines.extend(["", "## Comparator Sources"])
        for row in report["systems"]:
            if row["source_url"] == "local workspace":
                continue
            lines.append(f"- {row['name']}: {row['source_url']}")
        lines.extend(["", "## Limits"])
        for item in report["interpretation"]:
            lines.append(f"- {item}")
        return "\n".join(lines) + "\n"
