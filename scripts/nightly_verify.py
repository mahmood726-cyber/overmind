"""Overmind Nightly Verifier — multi-witness TruthCert verification across all projects.

Usage:
    python nightly_verify.py                      # Full run
    python nightly_verify.py --dry-run            # Show what would run, don't execute
    python nightly_verify.py --limit 10           # Cap at 10 projects
    python nightly_verify.py --timeout 60         # Per-project timeout in seconds
    python nightly_verify.py --min-risk high      # Only high-risk projects
    python nightly_verify.py --create-baselines   # (Future) Generate numerical baselines
"""
from __future__ import annotations

import argparse
import io
import json
import platform
import sys
import time
from datetime import datetime, UTC
from pathlib import Path

# Fix Python 3.13 + Windows WMI deadlock BEFORE any scipy/numpy import.
# Skip both monkey-patches when running under pytest:
#   - faulthandler.dump_traceback_later(exit=True) kills the test run after 60 min
#   - platform._wmi_query=lambda *a,**k: "" returns the wrong shape for Py3.13's
#     _win32_ver, which raises ValueError when hypothesis or other test deps call
#     platform.system().
if sys.platform == "win32" and "pytest" not in sys.modules:
    try:
        import faulthandler
        faulthandler.dump_traceback_later(3600, exit=True)  # safety net: kill if hung >60min
    except Exception:
        pass
    try:
        platform._wmi_query = lambda *a, **k: ""  # type: ignore[attr-defined]
    except Exception:
        pass

# Fix Windows cp1252 stdout — but ONLY when invoked as a script.
# Re-wrapping sys.stdout at import time corrupts pytest's capture tmpfile
# (lessons.md: "Module-level sys.stdout reassignment kills pytest capture").
if sys.platform == "win32" and "pytest" not in sys.modules:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overmind.storage.db import StateDatabase
from overmind.storage.models import MemoryRecord, VerificationResult, utc_now
from overmind.verification.truthcert_engine import TruthCertEngine
from overmind.runners.q_router import QRouter
from overmind.memory.store import MemoryStore
from overmind.memory.dream_engine import DreamEngine
from overmind.memory.audit_loop import AuditLoop

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DB_PATH = DATA_DIR / "state" / "overmind.db"
REPORT_DIR = DATA_DIR / "nightly_reports"
SKIP_PROJECTS = {
    "metasprint-autopilot-747b492b",                          # smoke import hangs (scipy deadlock)
    "superapp-3b1c175f",                                      # npm test hangs (Jest config)
    "metasprint-dta-5dffce53",                                # smoke import hangs (30K-line app)
    "lec-phase0-bundle-a2c59fad",                             # test suite hangs
    "hta-evidence-integrity-suite-dc1fe6c7",                  # test suite hangs (7946s last run)
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
    "new-app-a051eaea",                                       # registered test_command is a Selenium suite requiring a dev server on port 3005 + 82 Edge driver lifecycles — always times out. Real test surface is `npm run test` (vitest) which has 16 statistical-accuracy FAILs against R metafor (PM/SJ/HE estimators, prediction interval ordering). Needs dedicated stats-parity session.
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
    # `C:\Users\user\OneDrive - NHS\Documents\` was a scan root in
    # config/roots.yaml, so 37 already-canonical projects got auto-indexed
    # twice. Of those, 33 had a canonical sibling (in C:\Projects, C:\Models,
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
    "dta70-4b170dbc",                                         # OneDrive dup of DTA70 (canonical at C:\Projects\DTA70 fixed by DTA70@943a819)
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
    "rmstnma-1810584a",                                       # OneDrive dup of rmstnma (canonical at C:\Projects\rmstnma is UNVERIFIED)
    "worldipd-c534de53",                                      # OneDrive dup of WorldIPD
    "worldipd-private-3d6aeddf",                              # OneDrive dup of WorldIPD-private
    # Truly OneDrive-only (no canonical sibling) — skipped pending decision:
    "mahmood011025-5d5562d1",                                 # OneDrive-only date-named snapshot; promote to canonical or archive
    "metaoverfit-5f64eb8f",                                   # OneDrive-only research project; promote to canonical or archive
    "paper7-36216d64",                                        # OneDrive-only paper7 (publication-bias-related)
    "repo300-c9dc0181",                                       # OneDrive-only 300-repo bundle
    # Added 2026-05-04 — combined-witness budget exceeds --worker-timeout 900:
    "rct-extractor-v2-6c290650",                              # 851 tests pass locally in 58s, but combined test_suite + smoke + semgrep + pip_audit on a 30K-line codebase exceeds 900s. Run with `--worker-timeout 1800` for a clean read.
    "evidence-inference-4c874004",                            # 5 tests pass standalone but combined witness pipeline hangs at 900s — semgrep/pip_audit on a heavily-deps repo (transformers, evidence_inference, abstrarct, biomistral, etc.). Same `--worker-timeout 1800` recommendation.
}  # Projects that consistently hang during verification OR whose source path is missing OR whose source is broken enough to need dedicated repair


from overmind.integrations.sentinel_aggregator import collect as _collect_sentinel
from overmind.integrations.bypass_log_aggregator import collect as _collect_bypass


def collect_sentinel_findings() -> dict:
    """Thin wrapper around overmind.integrations.sentinel_aggregator.collect.

    Kept as a module-level name here so the nightly_verify tests and report
    can refer to it without importing the integration module directly.
    """
    return _collect_sentinel()


def _run_portfolio_sentinel_scan() -> dict:
    """Invoke `sentinel scan --portfolio` and summarise verdict counts.

    Portfolio-scope rules (registry_drift, path_not_exist, memory_paths_resolve,
    livingmeta_drift, agent_config_version_drift) run against the central
    project index rather than any one repo, so this scan surfaces drift that
    pre-push hooks never see because they fire per-repo-per-push.

    Fails soft: returns an error dict if the sentinel CLI isn't available,
    the scan crashes, or JSON parsing fails. Nightly verify must not crash
    here.

    Default project-index: C:/ProjectIndex (the canonical portfolio
    registry); override via OVERMIND_PROJECT_INDEX env var for tests.
    """
    import subprocess
    project_index = os.environ.get("OVERMIND_PROJECT_INDEX", "C:/ProjectIndex")
    if not Path(project_index).is_dir():
        return {"error": f"project-index not found: {project_index}"}
    try:
        # OVERMIND_PROJECT_INDEX is an internal-tooling env var sourced from the
        # operator's shell, not from any network surface. List-arg form,
        # shell=False — no shell injection vector.
        result = subprocess.run(
            [sys.executable, "-m", "sentinel", "scan",  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-tainted-env-args.dangerous-subprocess-use-tainted-env-args
             "--portfolio", "--project-index", project_index, "--json"],
            capture_output=True, text=True, timeout=180,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return {"error": f"{type(e).__name__}: {e}"}

    # exit 0 = clean, 1 = BLOCK findings, 2 = user error, 10 = internal
    if result.returncode >= 2:
        return {
            "error": f"sentinel scan exit {result.returncode}",
            "stderr": (result.stderr or "")[:500],
        }

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        return {"error": f"json decode: {e}", "stdout": result.stdout[:500]}

    verdicts = data.get("verdicts", [])
    by_severity = {"BLOCK": 0, "WARN": 0, "INFO": 0}
    by_rule: dict = {}
    for v in verdicts:
        sev = v.get("severity") or "UNKNOWN"
        by_severity[sev] = by_severity.get(sev, 0) + 1
        rid = v.get("rule_id") or "UNKNOWN"
        by_rule[rid] = by_rule.get(rid, 0) + 1

    return {
        "total_block": by_severity.get("BLOCK", 0),
        "total_warn": by_severity.get("WARN", 0),
        "total_info": by_severity.get("INFO", 0),
        "by_rule": by_rule,
        "project_index": project_index,
    }


def collect_bypass_findings(window_days: int = 7) -> dict:
    """Thin wrapper around bypass_log_aggregator.collect.

    Surfaces repeat Sentinel bypassers in the nightly report so enforcement
    can't go silently dark. Fails soft — a missing log is normal (nobody
    has bypassed yet).
    """
    return _collect_bypass(window_days=window_days)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Overmind Nightly Verifier")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without executing")
    parser.add_argument("--limit", type=int, default=50, help="Max projects to verify (default 50)")
    parser.add_argument("--timeout", type=int, default=120, help="Per-project test_suite witness timeout in seconds (default 120)")
    parser.add_argument("--worker-timeout", type=int, default=900,
                        help="Hard wall-clock kill for the witness-runner worker, "
                             "covers ALL witnesses combined (test_suite + smoke + "
                             "numerical_continuity + semgrep + pip_audit). Was 300 "
                             "before pip-audit + semgrep landed; 480 was insufficient "
                             "for projects with >2-min smoke/test commands. Default "
                             "900 gives ~3 min slack past worst-case combined budget.")
    parser.add_argument("--min-risk", choices=["medium", "medium_high", "high"], default="medium",
                        help="Minimum risk profile to verify (default medium)")
    parser.add_argument("--create-baselines", action="store_true",
                        help="Create numerical baselines for tier-3 projects (future work)")
    parser.add_argument("--projects-from-file", type=Path, default=None, metavar="PATH",
                        help="File of project paths (one per line) to verify. Bypasses "
                             "--min-risk and --limit so an operator can re-bundle a "
                             "specific set of paths (e.g. stale-UNVERIFIED projects) "
                             "without waiting for the natural risk-sorted cadence. "
                             "Lines starting with '#' and blank lines are ignored.")
    return parser.parse_args()


def _normalize_path(p) -> str:
    """Canonicalize a path for filter comparison: lowercase, forward-slash, no trailing sep."""
    import os
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
            # Operator-supplied list overrides the min_risk floor.
            rank = risk_order.get(p.risk_profile, 3)
        else:
            rank = risk_order.get(p.risk_profile, 3)
            if rank > min_rank:
                continue
        # Deduplicate by name (same project at different paths)
        if p.name.lower() in seen_names:
            continue
        seen_names.add(p.name.lower())
        candidates.append((rank, -p.advanced_math_score, p.project_id, p))

    candidates.sort()
    return [p for _, _, _, p in candidates[:limit]]


def _verify_worker(baselines_dir, test_timeout, project_dict, result_queue):
    """Worker function for multiprocessing-based verification."""
    try:
        from overmind.storage.models import ProjectRecord
        from overmind.verification.truthcert_engine import TruthCertEngine
        proj = ProjectRecord(**project_dict)
        engine = TruthCertEngine(baselines_dir=baselines_dir, test_timeout=test_timeout)
        bundle = engine.verify(proj)
        result_queue.put(("ok", bundle.to_dict()))
    except Exception as exc:
        result_queue.put(("error", str(exc)))


def _verify_with_timeout(engine, proj, timeout=900):
    """Run engine.verify in a separate process with a hard timeout.

    If the process hangs, it gets killed after `timeout` seconds.
    Returns a CertBundle (real or synthetic FAIL).
    """
    import multiprocessing
    from overmind.verification.scope_lock import WitnessResult
    from overmind.verification.cert_bundle import CertBundle

    result_queue = multiprocessing.Queue()
    worker = multiprocessing.Process(
        target=_verify_worker,
        args=(engine.baselines_dir, engine.test_suite_witness.timeout,
              proj.to_dict(), result_queue),
    )
    worker.start()
    # Poll is_alive() instead of join(timeout) — join hangs on Windows
    # when child subprocesses hold inherited pipe handles
    deadline = time.time() + timeout
    while worker.is_alive() and time.time() < deadline:
        time.sleep(2)

    if worker.is_alive():
        worker.terminate()
        time.sleep(3)
        if worker.is_alive():
            worker.kill()
            time.sleep(1)
        return CertBundle(
            project_id=proj.project_id,
            scope_lock=engine.build_scope_lock(proj),
            witness_results=[WitnessResult(
                witness_type="test_suite", verdict="FAIL", exit_code=-1,
                stdout="", stderr=f"Project hung — killed after {timeout}s",
                elapsed=float(timeout),
            )],
            verdict="FAIL",
            arbitration_reason=f"Hard timeout ({timeout}s) — process killed",
            timestamp=utc_now(),
        )

    def _cleanup_queue():
        try:
            result_queue.close()
            result_queue.join_thread()
        except Exception:
            pass

    try:
        status, data = result_queue.get_nowait()
    except Exception:
        _cleanup_queue()
        return CertBundle(
            project_id=proj.project_id,
            scope_lock=engine.build_scope_lock(proj),
            witness_results=[WitnessResult(
                witness_type="test_suite", verdict="FAIL", exit_code=-1,
                stdout="", stderr="Worker returned no result",
                elapsed=0.0,
            )],
            verdict="FAIL",
            arbitration_reason="Worker process returned no result",
            timestamp=utc_now(),
        )

    _cleanup_queue()

    if status == "error":
        return CertBundle(
            project_id=proj.project_id,
            scope_lock=engine.build_scope_lock(proj),
            witness_results=[WitnessResult(
                witness_type="test_suite", verdict="FAIL", exit_code=-1,
                stdout="", stderr=f"Worker error: {data}",
                elapsed=0.0,
            )],
            verdict="FAIL",
            arbitration_reason=f"Worker error: {data[:100]}",
            timestamp=utc_now(),
        )

    # Reconstruct CertBundle from dict
    from overmind.verification.scope_lock import ScopeLock
    scope_raw = data["scope_lock"]
    scope_lock = ScopeLock(
        project_id=scope_raw["project_id"],
        project_path=scope_raw["project_path"],
        risk_profile=scope_raw["risk_profile"],
        witness_count=scope_raw["witness_count"],
        test_command=scope_raw["test_command"],
        smoke_modules=tuple(scope_raw["smoke_modules"]),
        baseline_path=scope_raw.get("baseline_path"),
        expected_outcome=scope_raw["expected_outcome"],
        source_hash=scope_raw["source_hash"],
        created_at=scope_raw["created_at"],
    )
    witness_results = [WitnessResult(**w) for w in data["witness_results"]]
    return CertBundle(
        project_id=data["project_id"],
        scope_lock=scope_lock,
        witness_results=witness_results,
        verdict=data["verdict"],
        arbitration_reason=data["arbitration_reason"],
        timestamp=data["timestamp"],
        bundle_hash=data["bundle_hash"],
        failure_class=data.get("failure_class"),
    )


def _load_last_night_diagnoses(today_str: str, judge) -> list:
    """Load diagnoses from the most recent prior nightly report's bundles.

    Re-diagnoses REJECT/FAIL bundles from yesterday so Evolution Manager
    can track which failures resolved overnight.
    """
    from overmind.verification.cert_bundle import CertBundle
    from overmind.verification.scope_lock import ScopeLock, WitnessResult

    bundle_dirs = sorted((REPORT_DIR / "bundles").glob("*/"), reverse=True)
    last_dir = None
    for d in bundle_dirs:
        if d.name != today_str:
            last_dir = d
            break
    if not last_dir:
        return []

    diagnoses = []
    for bundle_file in last_dir.glob("*.json"):
        try:
            raw = json.loads(bundle_file.read_text(encoding="utf-8"))
            if raw.get("verdict") not in ("REJECT", "FAIL"):
                continue
            # Reconstruct CertBundle for Judge.diagnose()
            scope_raw = raw.get("scope_lock", {})
            scope_lock = ScopeLock(
                project_id=scope_raw.get("project_id", ""),
                project_path=scope_raw.get("project_path", ""),
                risk_profile=scope_raw.get("risk_profile", "medium"),
                witness_count=scope_raw.get("witness_count", 1),
                test_command=scope_raw.get("test_command", ""),
                smoke_modules=tuple(scope_raw.get("smoke_modules", [])),
                baseline_path=scope_raw.get("baseline_path"),
                expected_outcome=scope_raw.get("expected_outcome", "pass"),
                source_hash=scope_raw.get("source_hash", ""),
                created_at=scope_raw.get("created_at", ""),
            )
            witness_results = [
                WitnessResult(**w) for w in raw.get("witness_results", [])
            ]
            bundle = CertBundle(
                project_id=raw["project_id"],
                scope_lock=scope_lock,
                witness_results=witness_results,
                verdict=raw["verdict"],
                arbitration_reason=raw.get("arbitration_reason", ""),
                timestamp=raw.get("timestamp", ""),
                bundle_hash=raw.get("bundle_hash", ""),
            )
            diag = judge.diagnose(bundle)
            if diag:
                diagnoses.append(diag)
        except Exception:
            continue
    return diagnoses


def main() -> None:
    args = parse_args()
    run_start = datetime.now(UTC)
    print(f"Overmind Nightly Verifier - {run_start.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Config: limit={args.limit}, timeout={args.timeout}s, min_risk={args.min_risk}, dry_run={args.dry_run}")
    print()

    if args.create_baselines:
        print("NOTE: --create-baselines is not yet implemented. Baseline creation is future work.")
        print()

    db = StateDatabase(DB_PATH)
    try:
        _run_verification(db, args, run_start)
    except Exception as exc:
        print(f"\nFATAL ERROR: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        # Write crash log to file so failures are visible the next morning
        crash_path = REPORT_DIR / f"crash_{run_start.strftime('%Y-%m-%d')}.log"
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        crash_path.write_text(
            f"Nightly crash at {datetime.now(UTC).isoformat()}\n\n{traceback.format_exc()}",
            encoding="utf-8",
        )
    finally:
        db.close()


def _run_verification(db: StateDatabase, args: argparse.Namespace, run_start: datetime) -> None:
    engine = TruthCertEngine(
        baselines_dir=DATA_DIR / "baselines",
        test_timeout=args.timeout,
    )
    q_router = QRouter(db)
    memory_store = MemoryStore(db, DATA_DIR / "checkpoints", DATA_DIR / "logs")
    dream_engine = DreamEngine(db)
    audit_loop = AuditLoop(db)

    paths_filter = None
    if args.projects_from_file is not None:
        paths_filter = load_paths_filter(args.projects_from_file)
        print(f"Loaded {len(paths_filter)} target paths from {args.projects_from_file}")
    projects = select_projects(db, args.min_risk, args.limit, paths_filter=paths_filter)
    print(f"Selected {len(projects)} projects for verification")
    print()

    if args.dry_run:
        print("DRY RUN - would verify:")
        for p in projects:
            print(f"  {p.name} ({p.risk_profile}, math={p.advanced_math_score}) - {p.test_commands[0][:70]}")
        return

    # Run verification
    tick = int(time.time())
    results: list[dict] = []

    # Verdict counters
    certified = 0
    rejected = 0
    failed = 0
    single_pass = 0  # single-witness PASS (not CERTIFIED)
    unverified = 0   # tier-3 with missing numerical baseline (was miscounted as PASS before 2026-04-15)

    date_str = run_start.strftime("%Y-%m-%d")
    bundles_dir = REPORT_DIR / "bundles" / date_str
    bundles_dir.mkdir(parents=True, exist_ok=True)

    # When --projects-from-file is set, the operator explicitly wants these
    # projects re-bundled now; bypass both crash-resume and hash-skip caches.
    force_rerun = paths_filter is not None

    # Crash-resume: load progress from any interrupted run tonight
    progress_path = REPORT_DIR / f".progress_{date_str}.json"
    completed_ids: set[str] = set()
    if progress_path.exists() and not force_rerun:
        try:
            completed_ids = set(json.loads(progress_path.read_text(encoding="utf-8")).keys())
            print(f"Resuming: {len(completed_ids)} projects already verified tonight")
        except Exception:
            pass

    # Hash-skip: load only the most recent date's bundles (not all historical)
    yesterday_bundles: dict[str, dict] = {}
    if not force_rerun:
        bundle_dirs = sorted((REPORT_DIR / "bundles").glob("*/"), reverse=True)
        latest_bundle_dir = bundle_dirs[0] if bundle_dirs else None
        if latest_bundle_dir and latest_bundle_dir.name != date_str:
            for bundle_file in latest_bundle_dir.glob("*.json"):
                try:
                    b = json.loads(bundle_file.read_text(encoding="utf-8"))
                    pid = b.get("project_id", "")
                    if pid and b.get("verdict") == "CERTIFIED":
                        yesterday_bundles[pid] = b
                except Exception:
                    pass
    skipped_cached = 0

    for i, proj in enumerate(projects, 1):
        if proj.project_id in completed_ids:
            print(f"[{i}/{len(projects)}] {proj.name}... SKIPPED (already verified)")
            continue

        # Hash-skip: if source+test+HTML files unchanged since last CERTIFIED, skip re-verification.
        last_bundle = yesterday_bundles.get(proj.project_id)
        if last_bundle:
            current_hash = engine.build_scope_lock(proj).source_hash
            last_hash = last_bundle.get("scope_lock", {}).get("source_hash", "")
            if current_hash == last_hash and current_hash:
                print(f"[{i}/{len(projects)}] {proj.name}... CACHED (unchanged since last CERTIFIED)")
                skipped_cached += 1
                certified += 1
                continue

        print(f"[{i}/{len(projects)}] {proj.name}...", end=" ", flush=True)
        start = time.time()
        # Per-project wall-clock timeout using multiprocessing (can kill hung subprocesses)
        bundle = _verify_with_timeout(engine, proj, timeout=args.worker_timeout)
        elapsed = time.time() - start

        results.append({"project": proj, "bundle": bundle, "elapsed": elapsed})

        verdict = bundle.verdict
        print(f"{verdict} ({elapsed:.1f}s) [{bundle.arbitration_reason}]")

        # Tally
        if verdict == "CERTIFIED":
            certified += 1
        elif verdict == "REJECT":
            rejected += 1
        elif verdict == "FAIL":
            failed += 1
        elif verdict == "UNVERIFIED":
            # Tier-3 with missing numerical baseline — explicitly NOT a pass.
            unverified += 1
        elif verdict in ("PASS", "SKIP"):
            # Single-witness pass (arbitrator returned PASS because only 1 non-skip witness)
            single_pass += 1

        # Update Q-router (success = CERTIFIED or PASS; UNVERIFIED is NOT success)
        success = verdict in ("CERTIFIED", "PASS")
        q_router.record("claude", "verification", success)

        # Audit loop — build a VerificationResult from the bundle
        task_id = f"nightly_{proj.project_id[:12]}_{tick}"
        passed_witnesses = [w.witness_type for w in bundle.witness_results if w.verdict == "PASS"]
        failed_witnesses = [w.witness_type for w in bundle.witness_results if w.verdict == "FAIL"]
        skipped_witnesses = [w.witness_type for w in bundle.witness_results if w.verdict == "SKIP"]
        all_witness_types = [w.witness_type for w in bundle.witness_results]
        vr = VerificationResult(
            task_id=task_id,
            success=success,
            required_checks=all_witness_types,
            completed_checks=passed_witnesses,
            skipped_checks=skipped_witnesses + failed_witnesses,
            details=[bundle.arbitration_reason] + [
                w.stderr for w in bundle.witness_results if w.stderr
            ],
        )
        audit_loop.evaluate(proj.project_id, vr, tick=tick)

        # Save memory for non-passing projects (includes UNVERIFIED so the
        # missing-baseline case is surfaced in nightly memory for triage)
        if verdict not in ("CERTIFIED", "PASS"):
            detail_text = bundle.arbitration_reason
            memory_store.save(MemoryRecord(
                memory_id=f"nightly_fail_{proj.project_id[:8]}_{tick}",
                memory_type="regression",
                scope=proj.project_id,
                title=f"Nightly: {proj.name} {verdict}",
                content=(
                    f"Verification {verdict} on {run_start.strftime('%Y-%m-%d')}. "
                    f"{detail_text}. Risk: {proj.risk_profile}."
                ),
                source_task_id=task_id,
                source_tick=tick,
                relevance=1.0,
                confidence=0.95,
                tags=["nightly", "verification", verdict.lower()],
            ))
            # Also emit a typed bundle_failure memory so the dream engine
            # can cluster failures by failure_class across projects.
            if bundle.failure_class:
                memory_store.save(MemoryRecord(
                    memory_id=f"bundle_fail_{proj.project_id[:8]}_{tick}",
                    memory_type="bundle_failure",
                    scope=proj.project_id,
                    title=f"{proj.name}: {bundle.failure_class}",
                    content=(
                        f"{bundle.failure_class}: {bundle.arbitration_reason[:200]}"
                    ),
                    source_task_id=task_id,
                    source_tick=tick,
                    relevance=1.0,
                    confidence=0.9,
                    tags=[
                        "nightly", "bundle_failure",
                        f"failure_class:{bundle.failure_class}",
                        verdict.lower(),
                    ],
                ))

        # Save per-project bundle JSON
        bundle_path = bundles_dir / f"{proj.project_id[:16]}.json"
        bundle_path.write_text(json.dumps(bundle.to_dict(), indent=2), encoding="utf-8")

        # Crash-resume: save progress after each project
        try:
            progress = json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else {}
        except Exception:
            progress = {}
        progress[proj.project_id] = verdict
        progress_path.write_text(json.dumps(progress), encoding="utf-8")

    # Clean up progress file on successful completion
    if progress_path.exists():
        progress_path.unlink()

    # ─── Resilience checks (cross-domain patterns) ───────────────────────
    from overmind.verification.resilience import (
        SystemicAlertDetector, CommonCauseDetector,
        StabilityTracker, CanaryDetector, PreFixRiskChecker,
    )

    # 1. Systemic alert (immunology: fever response)
    systemic = SystemicAlertDetector()
    verdict_list = [{"project_id": r["project"].project_id, "verdict": r["bundle"].verdict,
                     "reason": r["bundle"].arbitration_reason} for r in results]
    alert = systemic.check(verdict_list)
    if alert.triggered:
        print(f"\n  *** SYSTEMIC ALERT: {alert.failure_rate:.0%} failure rate ***")
        print(f"  Dominant pattern: {alert.dominant_pattern} ({alert.affected_count}/{alert.total_count})")
        print(f"  Recommendation: {alert.recommendation}")

    # 3. Common-cause failure detection (nuclear: shared-mode analysis)
    common_cause = CommonCauseDetector()
    failure_data = []
    for r in results:
        if r["bundle"].verdict in ("FAIL", "REJECT"):
            evidence = " ".join(w.stderr + " " + w.stdout for w in r["bundle"].witness_results)
            failure_data.append({"project": r["project"].name, "evidence": evidence})
    cc_results = common_cause.detect(failure_data)
    for cc in cc_results:
        print(f"  Common-cause: {cc.shared_root} affects {len(cc.affected_projects)} projects")

    # 4. Stability tracking (pharma: batch stability)
    stability = StabilityTracker(DATA_DIR / "stability_state.json")
    stability_alerts = 0
    for r in results:
        ps = stability.update(r["project"].project_id, r["bundle"].verdict)
        if ps.alert:
            stability_alerts += 1
            print(f"  STABILITY BREAK: {r['project'].name} was stable for {ps.total_runs} runs, now {ps.last_verdict}")
    if stability_alerts:
        print(f"  {stability_alerts} stable projects just broke")

    # 5. Canary detection (ecology: ecosystem canaries)
    canary = CanaryDetector()
    current_verdicts = {r["project"].project_id: r["bundle"].verdict for r in results}
    project_names = {r["project"].project_id: r["project"].name for r in results}
    # Simple canary identification: low-risk projects that passed last time
    canary_ids = [pid for pid, state in stability.states.items()
                  if state.get("max_streak", 0) >= 3 and state.get("streak", 0) == 0]
    canary_alerts = canary.check_canaries(canary_ids, current_verdicts, project_names)
    for ca in canary_alerts:
        print(f"  CANARY: {ca.project_name} — {ca.reason}")

    # Store pre-fix risk checker for use in auto-fix phase
    risk_checker = PreFixRiskChecker(recent_hours=24)

    # CUSUM drift monitoring: track cumulative numerical drift over time
    from overmind.verification.cusum import CUSUMMonitor
    cusum = CUSUMMonitor(state_dir=DATA_DIR / "cusum_state")
    cusum_warnings = 0
    for r in results:
        bundle = r["bundle"]
        for w in bundle.witness_results:
            if w.witness_type == "numerical" and w.verdict == "PASS":
                # Load baseline to compare
                baseline_path = DATA_DIR / "baselines" / f"{r['project'].project_id[:20]}.json"
                if not baseline_path.exists():
                    # Try longer prefix
                    matches = list((DATA_DIR / "baselines").glob(f"{r['project'].project_id[:16]}*.json"))
                    if matches:
                        baseline_path = matches[0]
                if baseline_path.exists():
                    try:
                        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
                        # Parse actual values from witness stdout (probe output)
                        actual = json.loads(w.stdout) if w.stdout.strip().startswith("{") else {}
                        if actual and baseline.get("values"):
                            cr = cusum.check(r["project"].project_id, baseline["values"], actual, baseline.get("tolerance", 1e-6))
                            if cr.has_warning:
                                cusum_warnings += 1
                                for warn in cr.warnings:
                                    print(f"  CUSUM WARNING: {r['project'].name} — {warn}")
                            if cr.has_drift:
                                print(f"  CUSUM DRIFT: {r['project'].name} — {'; '.join(cr.drifts)}")
                    except (json.JSONDecodeError, OSError):
                        pass
    if cusum_warnings:
        print(f"CUSUM: {cusum_warnings} projects showing gradual drift")

    # Dream cycle
    print()
    print("Dreaming...", end=" ", flush=True)
    dream = dream_engine.dream()
    print(f"done ({dream['merges']} merges, {dream['archives']} archives)")

    # Wiki compilation
    print("Compiling wiki...", end=" ", flush=True)
    from overmind.wiki.compiler import WikiCompiler
    wiki_compiler = WikiCompiler(Path("C:/overmind/wiki"))
    wiki_stats = wiki_compiler.compile(
        bundles=[r["bundle"] for r in results],
        projects=[r["project"] for r in results],
    )
    print(f"done ({wiki_stats['articles_written']} articles, {wiki_stats['changes']} changes)")

    # Judge diagnoses for failures
    from overmind.diagnosis.judge import Judge
    judge = Judge()
    diagnoses = []
    for r in results:
        bundle = r["bundle"]
        if bundle.verdict in ("REJECT", "FAIL"):
            diag = judge.diagnose(bundle)
            if diag:
                diagnoses.append(diag)
                print(f"  Diagnosis: {r['project'].name} -> {diag.failure_type} ({diag.confidence:.0%}): {diag.recommended_action[:80]}")
    # Drop diagnoses into project repos as DECISIONS.md entries
    for diag in diagnoses:
        proj_match = next((r["project"] for r in results if r["project"].project_id == diag.project_id), None)
        if proj_match:
            decisions_path = Path(proj_match.root_path) / "DECISIONS.md"
            try:
                entry = f"- **{date_str}** [{diag.failure_type}] {diag.summary[:100]} — Action: {diag.recommended_action[:100]}\n"
                if decisions_path.exists():
                    existing = decisions_path.read_text(encoding="utf-8")
                    if entry.strip() not in existing:
                        decisions_path.write_text(existing + entry, encoding="utf-8")
                else:
                    decisions_path.write_text(f"# Overmind Decisions\n\n{entry}", encoding="utf-8")
            except OSError:
                pass  # Read-only or permission issue — skip silently
    if diagnoses:
        print(f"Diagnosed {len(diagnoses)} failures ({len(diagnoses)} decisions dropped)")

    # LLM-as-Judge: upgrade UNKNOWN diagnoses using Claude CLI
    unknown_count = sum(1 for d in diagnoses if d.failure_type == "UNKNOWN")
    if unknown_count > 0:
        print(f"\nLLM Judge: upgrading {unknown_count} UNKNOWN diagnoses...", end=" ", flush=True)
        try:
            from overmind.diagnosis.llm_judge import upgrade_unknown_diagnosis
            upgraded = 0
            for i, diag in enumerate(diagnoses):
                if diag.failure_type == "UNKNOWN":
                    new_diag = upgrade_unknown_diagnosis(diag, timeout=30)
                    if new_diag.failure_type != "UNKNOWN":
                        diagnoses[i] = new_diag
                        upgraded += 1
                        print(f"\n  {diag.project_id[:20]} -> {new_diag.failure_type} ({new_diag.confidence:.0%}): {new_diag.summary[:60]}", end="", flush=True)
            print(f"\n  Upgraded {upgraded}/{unknown_count}")
        except Exception as exc:
            print(f"failed ({exc})")

    # Auto-fix phase: attempt safe remediation for diagnosed failures
    from overmind.remediation.auto_fixer import AutoFixer
    auto_fixer = AutoFixer(
        baselines_dir=DATA_DIR / "baselines",
        probes_dir=DATA_DIR / "baseline_probes",
    )
    fixes_attempted = 0
    fixes_succeeded = 0
    fixes_committed = 0
    project_map = {r["project"].project_id: r["project"] for r in results}
    print()
    print("Auto-remediation...")
    for diag in diagnoses:
        proj = project_map.get(diag.project_id)
        if not proj:
            continue

        # Simple re-verify: run test command and check exit code
        def make_verify_fn(test_cmd, cwd):
            def verify(project_path):
                try:
                    from overmind.subprocess_utils import split_command
                    proc = subprocess.run(
                        split_command(test_cmd), cwd=cwd,
                        capture_output=True, text=True, timeout=120,
                    )
                    return proc.returncode == 0
                except Exception:
                    return False
            return verify

        # Pre-fix risk check (finance: pre-trade controls)
        risk = risk_checker.check(proj.root_path)
        if not risk.safe:
            print(f"  [SKIP] {proj.name}: {risk.reason}")
            continue

        verify_fn = make_verify_fn(proj.test_commands[0], proj.root_path) if proj.test_commands else None
        result = auto_fixer.attempt_fix(diag, proj.root_path, verify_fn=verify_fn)

        if result.fix_attempted:
            fixes_attempted += 1
            if result.fix_result and result.fix_result.success:
                fixes_succeeded += 1
                if result.committed:
                    fixes_committed += 1
            status = "FIXED" if result.fix_result and result.fix_result.success else "FAILED"
            print(f"  [{status}] {proj.name}: {result.detail}")
        elif "blocked" in result.detail.lower() or "no auto-fix" in result.detail.lower():
            pass  # Silent skip for unfixable types
        else:
            print(f"  [SKIP] {proj.name}: {result.detail}")

    # LLM repair: attempt Claude-powered fixes for remaining failures
    unfixed_diags = [d for d in diagnoses if d.failure_type not in ("FORMULA_ERROR", "FLOAT_PRECISION", "NUMERICAL_DRIFT", "UNKNOWN")]
    unfixed_diags = [d for d in unfixed_diags if d.project_id in project_map]
    if unfixed_diags:
        try:
            from overmind.remediation.llm_repair import LLMRepairer
            llm_repairer = LLMRepairer(timeout=60)
            llm_attempted = 0
            llm_succeeded = 0
            for diag in unfixed_diags[:5]:  # Cap at 5 LLM calls per run
                proj = project_map.get(diag.project_id)
                if not proj or not llm_repairer.can_fix(diag):
                    continue
                risk = risk_checker.check(proj.root_path)
                if not risk.safe:
                    continue
                verify_fn = make_verify_fn(proj.test_commands[0], proj.root_path) if proj.test_commands else None
                llm_result = llm_repairer.attempt_repair(diag, proj.root_path, verify_fn=verify_fn)
                if llm_result.success:
                    llm_succeeded += 1
                    print(f"  [LLM-FIXED] {proj.name}: {llm_result.detail}")
                elif llm_result.action_taken != "skip":
                    print(f"  [LLM-FAIL] {proj.name}: {llm_result.detail}")
                llm_attempted += 1
            if llm_attempted:
                print(f"LLM repair: {llm_succeeded}/{llm_attempted} succeeded")
        except Exception as exc:
            print(f"LLM repair: skipped ({exc})")

    if fixes_attempted:
        print(f"Auto-fix: {fixes_succeeded}/{fixes_attempted} succeeded")
    else:
        print("Auto-fix: no fixable failures found")
    print()

    # Evolution manager
    from overmind.evolution.manager import EvolutionManager
    evo_mgr = EvolutionManager(Path("C:/overmind/wiki"))
    # Determine which projects resolved (were FAIL/REJECT last night, now CERTIFIED/PASS)
    resolved_ids = set()
    for r in results:
        if r["bundle"].verdict in ("CERTIFIED", "PASS"):
            resolved_ids.add(r["project"].project_id)
    # Load last night's diagnoses so Evolution Manager can track resolutions
    last_night_diagnoses = _load_last_night_diagnoses(date_str, judge)
    evo_stats = evo_mgr.evolve(
        diagnoses=diagnoses,
        last_night_diagnoses=last_night_diagnoses,
        resolved_project_ids=resolved_ids,
    )
    if evo_stats["new_recipes"] or evo_stats["resolutions"]:
        print(f"Evolution: {evo_stats['new_recipes']} new recipes, {evo_stats['resolutions']} resolutions, {evo_stats['proven_recipes']} proven")

    # Skill library: promote proven recipes to reusable skills
    from overmind.evolution.skill_library import SkillLibrary
    skill_lib = SkillLibrary(Path("C:/overmind/wiki/SKILLS.json"))
    promoted = 0
    recipes = evo_mgr._load_recipes()
    for recipe in recipes:
        if recipe.is_proven():
            skill = skill_lib.promote_recipe(recipe)
            if skill:
                promoted += 1
    demoted = skill_lib.demote_stale()
    stats = skill_lib.stats()
    if promoted or demoted or stats["total_skills"]:
        print(f"Skills: {stats['total_skills']} total, {promoted} promoted, {demoted} demoted")
    print()

    # Prune old checkpoints to prevent unbounded SQLite growth
    pruned = db.prune_checkpoints(keep=100)
    if pruned:
        print(f"Pruned {pruned} old checkpoints")

    # Generate report
    total_time = sum(r["elapsed"] for r in results)
    n = len(results)

    report = {
        "timestamp": run_start.isoformat(),
        "total_projects": n,
        "certified": certified,
        "rejected": rejected,
        "failed": failed,
        "single_pass": single_pass,
        "unverified": unverified,
        "total_time_seconds": round(total_time, 1),
        "dream": {
            "merges": dream["merges"],
            "archives": dream["archives"],
            "memories_before": dream["memories_before"],
            "memories_after": dream["memories_after"],
        },
        "projects": [],
    }
    for r in results:
        b = r["bundle"]
        report["projects"].append({
            "name": r["project"].name,
            "path": r["project"].root_path,
            "risk": r["project"].risk_profile,
            "math_score": r["project"].advanced_math_score,
            "verdict": b.verdict,
            "bundle_hash": b.bundle_hash,
            "witness_count": len([w for w in b.witness_results if w.verdict != "SKIP"]),
            "elapsed": round(r["elapsed"], 1),
            "arbitration_reason": b.arbitration_reason,
        })

    # Aggregate Sentinel findings portfolio-wide (STUCK_FAILURES.md per repo).
    # Fails soft — sentinel integration errors must not crash nightly verify.
    try:
        report["sentinel"] = collect_sentinel_findings()
    except Exception as e:
        report["sentinel"] = {"error": f"aggregation crashed: {type(e).__name__}: {e}"}

    # Run LIVE portfolio-scope Sentinel scan. Unlike collect_sentinel_findings
    # which reads the pre-existing STUCK_FAILURES/sentinel-findings files
    # (potentially stale if a repo hasn't been pushed recently), this actively
    # invokes `sentinel scan --portfolio` to surface current latent state:
    # registry drift, memory-path resolution, livingmeta drift, etc.
    # Added 2026-04-16 late-night to close the "pre-push gaps hide latent
    # issues between pushes" gap.
    try:
        report["sentinel_portfolio_live"] = _run_portfolio_sentinel_scan()
    except Exception as e:
        report["sentinel_portfolio_live"] = {
            "error": f"live scan crashed: {type(e).__name__}: {e}",
        }

    # Surface last 7 days of Sentinel bypass events. Empty = enforcement
    # healthy; nonzero = someone bypassed and may have shipped a real violation.
    try:
        report["bypass"] = collect_bypass_findings(window_days=7)
    except Exception as e:
        report["bypass"] = {"error": f"bypass aggregation crashed: {type(e).__name__}: {e}"}

    # Write JSON report
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = REPORT_DIR / f"nightly_{date_str}.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Write Markdown report
    md_path = REPORT_DIR / f"nightly_{date_str}.md"
    md_lines = [
        f"# Nightly Verification Report - {date_str}",
        "",
        f"**{certified}/{n + skipped_cached} CERTIFIED** ({skipped_cached} cached) | {failed} FAIL | {rejected} REJECT | {single_pass} single-witness (PASS) | {unverified} UNVERIFIED",
        "",
        "```mermaid",
        "pie title Nightly Verdicts",
    ]
    if certified:
        md_lines.append(f'    "CERTIFIED" : {certified}')
    if single_pass:
        md_lines.append(f'    "PASS" : {single_pass}')
    if unverified:
        md_lines.append(f'    "UNVERIFIED" : {unverified}')
    if rejected:
        md_lines.append(f'    "REJECT" : {rejected}')
    if failed:
        md_lines.append(f'    "FAIL" : {failed}')
    md_lines.extend(["```", ""])

    # Top proven recipes (from Evolution Manager)
    procedures_path = Path("C:/overmind/wiki/PROCEDURES.md")
    if procedures_path.exists():
        import re as _re
        proc_content = procedures_path.read_text(encoding="utf-8")
        proven_rows = _re.findall(
            r"^\| ([^|]+)\| ([^|]+)\| ([^|]+)\| (\d+)\s*\| (\d+)\s*\| (\d+)%",
            proc_content, _re.MULTILINE,
        )
        proven = [(r[0].strip(), r[2].strip(), int(r[5])) for r in proven_rows
                  if not r[0].strip().startswith("Recipe") and int(r[5]) > 0]
        if proven:
            proven.sort(key=lambda x: -x[2])
            md_lines.extend(["**Top proven fixes:**"])
            for recipe_id, fix, conf in proven[:3]:
                md_lines.append(f"- `{recipe_id}`: {fix} ({conf}% confidence)")
            md_lines.append("")

    # CERTIFIED table
    certified_rows = [r for r in results if r["bundle"].verdict == "CERTIFIED"]
    if certified_rows:
        md_lines.extend([
            "## Certified",
            "",
            "| Project | Risk | Math | Witnesses | Bundle Hash | Time |",
            "|---------|------|------|-----------|-------------|------|",
        ])
        for r in certified_rows:
            b = r["bundle"]
            wc = len([w for w in b.witness_results if w.verdict != "SKIP"])
            md_lines.append(
                f"| {r['project'].name} | {r['project'].risk_profile} | "
                f"{r['project'].advanced_math_score} | {wc} | `{b.bundle_hash}` | {r['elapsed']:.1f}s |"
            )
        md_lines.append("")

    # Single-witness PASS table
    pass_rows = [r for r in results if r["bundle"].verdict == "PASS"]
    if pass_rows:
        md_lines.extend([
            "## Single-Witness Pass",
            "",
            "| Project | Risk | Math | Time |",
            "|---------|------|------|------|",
        ])
        for r in pass_rows:
            md_lines.append(
                f"| {r['project'].name} | {r['project'].risk_profile} | "
                f"{r['project'].advanced_math_score} | {r['elapsed']:.1f}s |"
            )
        md_lines.append("")

    # UNVERIFIED section (tier-3 with missing numerical baseline — NOT a release pass)
    unverified_rows = [r for r in results if r["bundle"].verdict == "UNVERIFIED"]
    if unverified_rows:
        md_lines.extend([
            "## Unverified (Missing Numerical Baseline)",
            "",
            "_Tier-3 projects where test + smoke PASSED but the numerical witness SKIPPED"
            " because the baseline file is missing. Per `testing.md`: NOT a release pass._",
            "",
            "| Project | Risk | Math | Witnesses | Reason |",
            "|---------|------|------|-----------|--------|",
        ])
        for r in unverified_rows:
            b = r["bundle"]
            witnesses = ", ".join(f"{w.witness_type}={w.verdict}" for w in b.witness_results)
            md_lines.append(
                f"| {r['project'].name} | {r['project'].risk_profile} | "
                f"{r['project'].advanced_math_score} | {witnesses} | {b.arbitration_reason} |"
            )
        md_lines.append("")

    # REJECT section
    reject_rows = [r for r in results if r["bundle"].verdict == "REJECT"]
    if reject_rows:
        md_lines.extend(["## Rejected (Witness Disagreement)", ""])
        for r in reject_rows:
            b = r["bundle"]
            md_lines.append(f"### {r['project'].name}")
            md_lines.append(f"**Reason:** {b.arbitration_reason}")
            md_lines.append("")
            md_lines.append("| Witness | Verdict | Details |")
            md_lines.append("|---------|---------|---------|")
            for w in b.witness_results:
                detail = (w.stderr or w.stdout or "")[:120].replace("\n", " ")
                md_lines.append(f"| {w.witness_type} | {w.verdict} | {detail} |")
            md_lines.append("")

    # FAIL section
    fail_rows = [r for r in results if r["bundle"].verdict == "FAIL"]
    if fail_rows:
        md_lines.extend(["## Failed (All Witnesses)", ""])
        for r in fail_rows:
            b = r["bundle"]
            md_lines.append(f"### {r['project'].name}")
            md_lines.append(f"**Reason:** {b.arbitration_reason}")
            md_lines.append("")
            for w in b.witness_results:
                if w.verdict == "FAIL":
                    detail = (w.stderr or w.stdout or "")[:300]
                    md_lines.append(f"**{w.witness_type}:** {detail}")
            md_lines.append("")

    # Sentinel portfolio findings section
    sentinel = report.get("sentinel") or {}
    if sentinel.get("error"):
        md_lines.extend([
            "## Sentinel Portfolio Findings",
            "",
            f"_Aggregation error: {sentinel['error']}_",
            "",
        ])
    elif sentinel.get("total_block") or sentinel.get("total_warn"):
        md_lines.extend([
            "## Sentinel Portfolio Findings",
            "",
            f"**{sentinel['total_block']} BLOCK** / {sentinel['total_warn']} WARN "
            f"across {sentinel['total_repos_with_findings']} repos",
            "",
            "### Top repos by finding count",
            "",
            "| Repo | BLOCK | WARN |",
            "|------|-------|------|",
        ])
        for r in sentinel.get("top_repos", [])[:10]:
            md_lines.append(f"| `{r['repo']}` | {r['block']} | {r['warn']} |")
        md_lines.extend([
            "",
            "### Top rules fired",
            "",
            "| Rule | Count |",
            "|------|-------|",
        ])
        for r in sentinel.get("top_rules", [])[:10]:
            md_lines.append(f"| `{r['rule_id']}` | {r['count']} |")
        md_lines.append("")

    # Sentinel bypass log — surface repeat bypassers so enforcement can't
    # silently go dark. Empty log = healthy (rendered only if nonzero).
    bypass = report.get("bypass") or {}
    if bypass.get("error"):
        md_lines.extend([
            "## Sentinel Bypass Log",
            "",
            f"_Aggregation error: {bypass['error']}_",
            "",
        ])
    elif bypass.get("total_bypasses", 0) > 0:
        window = bypass.get("window_days", 7)
        total = bypass["total_bypasses"]
        md_lines.extend([
            "## Sentinel Bypass Log",
            "",
            f"**{total} `SENTINEL_BYPASS=1 git push` event(s) in last {window} days.** "
            "If any repo is repeat-bypassing, enforcement is silently off for that repo.",
            "",
            "| Repo | Bypasses | Latest |",
            "|------|----------|--------|",
        ])
        for r in bypass.get("repos", [])[:10]:
            md_lines.append(f"| `{r['repo']}` | {r['count']} | {r['latest']} |")
        md_lines.append("")

    md_lines.extend([
        f"Dream: {dream['merges']} merges, {dream['archives']} archives, "
        f"{dream['memories_before']}->{dream['memories_after']} memories",
    ])

    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    # Also write latest.json for dashboard consumption
    (REPORT_DIR / "latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    print("=" * 60)
    print("NIGHTLY VERIFICATION COMPLETE")
    print(f"  {certified}/{n} CERTIFIED | {failed} FAIL | {rejected} REJECT | {single_pass} PASS | {unverified} UNVERIFIED")
    print(f"  Total time: {total_time:.0f}s")
    print(f"  Report: {md_path}")
    print(f"  Bundles: {bundles_dir}")
    print("=" * 60)

    # Generate HTML morning insights dashboard
    try:
        from scripts.generate_dashboard import load_latest_report, load_report_history, load_cusum_warnings, load_skills, generate_html
        dashboard_dir = Path("C:/overmind/dashboard")
        dashboard_dir.mkdir(parents=True, exist_ok=True)
        dash_report = load_latest_report()
        if dash_report:
            html = generate_html(dash_report, load_report_history(7), load_cusum_warnings(), load_skills())
            dash_path = dashboard_dir / "index.html"
            dash_path.write_text(html, encoding="utf-8")
            print(f"  Dashboard: {dash_path}")
            # Auto-open in morning (only if not 3 AM — skip if running at night)
            import webbrowser
            hour = datetime.now().hour
            if 6 <= hour <= 22:  # Only open during waking hours
                webbrowser.open(str(dash_path))
    except Exception as exc:
        print(f"  Dashboard: failed ({exc})")


if __name__ == "__main__":
    main()
