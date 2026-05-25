"""Project selection helpers extracted from scripts/nightly_verify.py.

Holds SKIP_PROJECTS, PROJECT_WORKER_TIMEOUTS, and the candidate-list
helpers. nightly_verify.py re-exports each public symbol so test
fixtures referring to `nightly_verify.SKIP_PROJECTS` /
`nightly_verify.select_projects` continue to work unchanged.
"""
from __future__ import annotations

import os
from pathlib import Path

from overmind.storage.db import StateDatabase


SKIP_PROJECTS = {
    # 2026-05-04 attempt to unskip metasprint-autopilot worked partially:
    # metasprint-autopilot@ca56f95 fixed the pipeline/__init__.py path issue
    # so `import pipeline.auto_cluster` works. test_suite + semgrep + pip_audit
    # + numerical + numerical_continuity all PASS now. But smoke witness still
    # FAILs because two OTHER modules (truthcert1_work/update_forest_plot.py
    # and validation/check_4_recent_high_quality_metas.py) read hardcoded
    # files at import time → FileNotFoundError. Per-module wrapping needed.
    # metasprint-autopilot-747b492b UNSKIPPED 2026-05-04 (final-final): batch
    # fix shipped at metasprint-autopilot@3748cb4 — path-injecting __init__.py
    # in 4 namespace dirs (validation/, truthcert1_work/, .../tools/,
    # .../PLOS_ONE_Submission/) plus `if __name__ != "__main__": sys.exit(0)`
    # guards on 11 standalone Selenium/orchestrator scripts. All 40 smoke
    # modules now import clean.
    # superapp-3b1c175f UNSKIPPED 2026-05-05: Bayesian engine fixes shipped
    # at superapp@56dbaff cleared the "Cannot read properties of undefined"
    # cascade and the DIC deviance.reduce bug. jest now completes in 118s
    # (161/178 passing); 17 remaining failures are unrelated contract gaps
    # in bayesianModelComparison + diagnostic field-name mismatches.
    "metasprint-dta-5dffce53",                                # smoke import hangs (30K-line app)
    "lec-phase0-bundle-a2c59fad",                             # test suite hangs
    # mem-ecosystem-model-8299ceea was QUARANTINED then UNSKIPPED 2026-05-06:
    # the 2026-05-04 [46/50] hang on this project tripped the 14400s
    # faulthandler safety-net and left Task Scheduler stuck in
    # ERROR_SERVICE_ALREADY_RUNNING for 3 days. Per-witness probe 2026-05-06
    # confirmed all 4 witnesses (test_suite 0.6s, smoke 10.3s, semgrep 24.6s,
    # pip_audit 62.7s) PASS cleanly — final CERTIFIED in 112s. Almost
    # certainly a transient network call (pip-audit PyPI or semgrep registry).
    # The new per-iteration partial-report-flush defense added in the same
    # change means a recurrence will no longer poison the night — the
    # partial verdict survives even os._exit(). If it hangs systematically,
    # add a PROJECT_WORKER_TIMEOUTS entry, NOT a blanket SKIP.
    # hta-evidence-integrity-suite-dc1fe6c7 UNSKIPPED 2026-05-04: full pytest -q
    # passes 1/1 in 0.5s. Earlier "hangs (7946s)" note is from a stale layout —
    # the manuscript-numbers verifier was wrapped behind a fast pytest contract.
    # meta-ecosystem-model-3d6353ab UNSKIPPED 2026-05-04: path is present at
    # C:\Models\Meta_Ecosystem_Model and `python tests/verify_manuscript_numbers.py`
    # passes 109/109 in 5s. The 2026-04-14 "genuinely absent" note is stale.
    # ipd-qma-project-b5694da4 REPAIRED 2026-04-14: 8 files + truncated
    # ipd_qma_ml.py header reconstructed, all 4 .py files compile, smoke
    # PASS, tests 59/1-skipped. Project also requires a probe script
    # (see data/baseline_probes/TODO.md) before it can earn CERTIFIED.
    # llm-meta-analysis-8e261d9f REPAIRED 2026-04-14: 2 syntax errors fixed
    # (meta_regression, report_generator), 3 broken sibling imports restored
    # to relative (.models.model, .statistical_framework), backward-compat
    # aliases added to power_analysis.py (PowerAnalysis,
    # SampleSizeCalculator). LLM backend adapters (alpaca/biomistral/gemma/
    # llama3/olmo/pmc_llama/etc.) added to truthcert_engine._SKIP_FILES as
    # they need remote APIs or heavy model downloads to import. Smoke now
    # PASS across 40 discovered modules.
    # new-app-a051eaea UNSKIPPED 2026-05-04: vitest now passes 92/92 in 2.7s
    # (the 16 stats-parity FAILs from the earlier note have been resolved).
    # Selenium tests/test_ui.py was the FIRST test_command and Overmind only
    # reads test_commands[0] — the DB record was directly updated 2026-05-04
    # to put `npm run test` first so the fast vitest path runs by default.
    # If discovery re-scans and reorders, this skip may need to come back.
    # Added 2026-04-25 after audit of nightly 2026-04-25 FAILs (5 FAILs, all systemic-not-code):
    "cbamm-c5df0bd2",                                         # path missing on disk (Archive/Stale-Projects/Cbamm) — already archived, registry not yet reconciled
    "cbamm-c0fea32f",                                         # archived dup (Archive/Stale-Projects/CBAMM_CLEAN_COMPLETE/...)
    "cbamm-0820ec88",                                         # OneDrive/Documents/Cbamm — same Cbamm via OneDrive sync; R devtools test command times out
    "pairwise70-900619fe",                                    # path missing on disk (Models/Pairwise70) — superseded by Pairwise70 corpus living in MetaAudit subdirs
    "pairwise70-4020df78",                                    # Projects/Pairwise70 — selenium_comprehensive_test.py hangs the witness (Selenium driver lifecycle); not a code regression
    "pairwise70-5049aa49",                                    # OneDrive/Documents/Pairwise70 — same selenium hang via OneDrive copy
    "pairwise70-results-v2-fa19e3ac",                         # data/Research-Archives/Pairwise70_Results_v2 — archive snapshot, not active code
    "pairwise70-results-v2-23d13a6c",                         # OneDrive/Documents/Pairwise70_Results_v2 — same archive via OneDrive
    "html-apps-6eaac579",                                     # the HTML-apps scan root is a directory of standalone single-file HTML demos, not a single project — discovery picked it up wrongly; 300s timeout because no coherent test surface
    "user-ecc0a382",                                          # the home-directory scan root is NOT a project — 300s timeout on whatever heuristic test command was inferred from dotfiles
    # Added 2026-04-25 (env-bound REJECT cleanup):
    # fatiha-project-a8ec1065 UNSKIPPED 2026-05-04: renv 1.1.5 is now installed
    # locally + testthat + shiny + 60-package renv.lock snapshot, AND the
    # tests/testthat/setup.R fix (FATIHA_Project@8b7c7be) loads the SYNTHESIS
    # package via pkgload before testthat runs. Verified locally:
    # `Rscript -e "testthat::test_dir('tests/testthat')"` → 82 passed.

    # Added 2026-05-04 — OneDrive duplicates discovered en masse.
    # The OneDrive Documents tree was a scan root in
    # config/roots.yaml, so 37 already-canonical projects got auto-indexed
    # twice. Of those, 33 had a canonical sibling (in <home>/Projects, <home>/Models,
    # etc.) so the OneDrive copy is redundant. The 4 truly OneDrive-only ones
    # (mahmood011025, metaoverfit, paper7, repo300) are skipped pending a
    # decision on whether to re-home them to canonical paths. Companion fix:
    # OneDrive removed from config/roots.yaml so future scans won't repopulate.
    "501mlm-6126e03d",                                        # OneDrive dup of 501MLM
    "501mlm-submission-ae2e374e",                             # OneDrive dup of 501MLM_Submission
    "786-miii-meta-a6d355d5",                                 # OneDrive dup of 786-MIII meta
    "a-7bca3193",                                             # OneDrive dup of `a` (one-letter dir)
    "area1-small-sample-analysis-1fbec3af",                   # OneDrive dup of area1_small_sample_analysis
    "chat2-b1718ad7",                                         # OneDrive dup of chat2
    "chat3-95d03df4",                                         # OneDrive dup of chat3
    "chatpaper-7610d635",                                     # OneDrive dup of chatpaper
    "claude2-2c0296b2",                                       # OneDrive dup of claude2
    "clauderepo-a6002185",                                    # OneDrive dup of clauderepo
    "cochranedataextractor-e1ffd99a",                         # OneDrive dup of CochraneDataExtractor
    "decision-wasm-57802073",                                 # OneDrive dup of decision-wasm
    "dta70-4b170dbc",                                         # OneDrive dup of DTA70 (canonical fixed by DTA70@943a819)
    "hfn786-58381c44",                                        # OneDrive dup of HFN786
    "kmcurve-cf94c326",                                       # OneDrive dup of KMcurve
    "lfa-36caf1fb",                                           # OneDrive dup of LFA
    "lfahfn-2585f64f",                                        # OneDrive dup of LFAHFN
    "livingmeta-watchman-amulet-6abff0f3",                    # OneDrive dup of LivingMeta_Watchman_Amulet
    "mlmresearch-603c45f0",                                   # OneDrive dup of MLMResearch
    "multilevelerror-8509b533",                               # OneDrive dup of Multilevelerror
    "multivar-98711bfe",                                      # OneDrive dup of multivar
    "nmapaper111025-1489aebd",                                # OneDrive dup of nmapaper111025
    "pair786-75c04b41",                                       # OneDrive dup of Pair786
    "paper-fa34cea9",                                         # OneDrive dup of Paper
    "paper1-0c592fd8",                                        # OneDrive dup of Paper1
    "paper2-111025-2e8eae70",                                 # OneDrive dup of Paper2.111025
    "repo100-8f261f45",                                       # OneDrive dup of repo100
    "rmstnma-1810584a",                                       # OneDrive dup of rmstnma (canonical is UNVERIFIED)
    "worldipd-c534de53",                                      # OneDrive dup of WorldIPD
    "worldipd-private-3d6aeddf",                              # OneDrive dup of WorldIPD-private
    # Truly OneDrive-only (no canonical sibling) — skipped pending decision:
    "mahmood011025-5d5562d1",                                 # OneDrive-only date-named snapshot; promote to canonical or archive
    "metaoverfit-5f64eb8f",                                   # OneDrive-only research project; promote to canonical or archive
    "paper7-36216d64",                                        # OneDrive-only paper7 (publication-bias-related)
    "repo300-c9dc0181",                                       # OneDrive-only 300-repo bundle
    # rct-extractor-v2 + evidence-inference UNSKIPPED 2026-05-05: the
    # per-project witness-timeout-override mechanism shipped this turn
    # (PROJECT_WORKER_TIMEOUTS dict below). Both now have a 3600s budget
    # so their combined witness pipeline can complete.
    # rct-extractor-v2 + evidence-inference RE-SKIPPED 2026-05-06: empirically
    # even with 7200s+ worker budget both projects hit the worker timeout wall.
    # Direct test_command runs in seconds (rct: 23 tests/2.7s, evi: 5+3 skip
    # in 3.3s) but Overmind's witness pipeline hangs — likely SemgrepWitness
    # on the 30K-line repos OR PipAuditWitness on heavy ML deps tree
    # (transformers/biomistral/spacy). subprocess.run timeouts don't always
    # fire on Windows when child processes hold inherited pipe handles
    # (lessons.md 2026-04-30). Skipping until witness scope is reduced for
    # these heavy projects (e.g. tier downgrade, semgrep skip-list).
    "rct-extractor-v2-6c290650",
    "evidence-inference-4c874004",
}  # Projects that consistently hang during verification OR whose source path is missing OR whose source is broken enough to need dedicated repair


# Per-project worker-timeout overrides (in seconds). For projects whose
# combined witness pipeline (test_suite + smoke + semgrep + pip_audit +
# numerical) genuinely exceeds the default --worker-timeout, encode the
# override here instead of bumping the global default (which would slow
# every other project's worst-case ceiling). The lookup uses project_id.
PROJECT_WORKER_TIMEOUTS: dict[str, int] = {
    # Both projects confirmed exceed 3600s on this machine (the bg run on
    # 2026-05-05 killed both at exactly 3604s). 7200s gives the combined
    # test_suite + smoke + semgrep + pip_audit + numerical pipeline more
    # headroom. Still under the 14400s script-level faulthandler.
    "rct-extractor-v2-6c290650": 13000,    # 851 pytest tests + 30K-line semgrep — 7200s wall hit 2026-05-05
    "evidence-inference-4c874004": 13000,  # transformers/biomistral deps tree — 7200s wall hit 2026-05-05
    # superapp killed at 1800s on 2026-05-05 with witness_count=1 (test_suite
    # alone hit the wall). Direct npm test --runInBand takes ~1200s; Overmind's
    # subprocess wrapper adds enough overhead to push past 1800s. 3600s gives
    # 3x margin over the direct measurement.
    "superapp-3b1c175f": 3600,            # 207 jest tests via --runInBand
}


def _normalize_path(p) -> str:
    """Canonicalize a path for filter comparison: lowercase, forward-slash, no trailing sep."""
    s = os.path.normpath(str(p)).replace("\\", "/").rstrip("/").lower()
    return s


def load_paths_filter(path) -> set[str]:
    """Read a paths file (one path per line) and return the normalized set.

    Skips blank lines and lines starting with '#'. Whitespace is stripped.
    Raises FileNotFoundError if the file is missing.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"--projects-from-file: {p}")
    out: set[str] = set()
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.add(_normalize_path(line))
    return out


def select_projects(db: StateDatabase, min_risk: str, limit: int,
                    paths_filter: set[str] | None = None) -> list:
    """Select projects with test commands, sorted by risk and math score.

    When paths_filter is provided, only projects whose normalized root_path
    is in the set are considered, and the min_risk floor is bypassed (the
    operator's explicit list wins). The limit still applies, so callers
    that want all matching projects should pass a generous limit.
    """
    risk_order = {"high": 0, "medium_high": 1, "medium": 2}
    min_rank = risk_order.get(min_risk, 2)

    projects = db.list_projects()
    candidates = []
    seen_names = set()
    for p in projects:
        if p.project_id in SKIP_PROJECTS:
            continue
        if not p.test_commands:
            continue
        if paths_filter is not None:
            if _normalize_path(p.root_path) not in paths_filter:
                continue
            rank = risk_order.get(p.risk_profile, 3)
        else:
            rank = risk_order.get(p.risk_profile, 3)
            if rank > min_rank:
                continue
        if p.name.lower() in seen_names:
            continue
        seen_names.add(p.name.lower())
        candidates.append((rank, -p.advanced_math_score, p.project_id, p))

    candidates.sort()
    return [p for _, _, _, p in candidates[:limit]]
