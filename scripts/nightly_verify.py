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

# Fix Python 3.13 + Windows WMI deadlock BEFORE any scipy/numpy import
if sys.platform == "win32":
    try:
        import faulthandler
        faulthandler.dump_traceback_later(1800, exit=True)  # safety net: kill if hung >30min
    except Exception:
        pass
    try:
        platform._wmi_query = lambda *a, **k: ""  # type: ignore[attr-defined]
    except Exception:
        pass

# Fix Windows cp1252 stdout
if sys.platform == "win32":
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
SKIP_PROJECTS = set()  # Add project_ids that always hang


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Overmind Nightly Verifier")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without executing")
    parser.add_argument("--limit", type=int, default=50, help="Max projects to verify (default 50)")
    parser.add_argument("--timeout", type=int, default=120, help="Per-project timeout in seconds (default 120)")
    parser.add_argument("--min-risk", choices=["medium", "medium_high", "high"], default="medium",
                        help="Minimum risk profile to verify (default medium)")
    parser.add_argument("--create-baselines", action="store_true",
                        help="Create numerical baselines for tier-3 projects (future work)")
    return parser.parse_args()


def select_projects(db: StateDatabase, min_risk: str, limit: int) -> list:
    """Select projects with test commands, sorted by risk and math score."""
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


def _verify_with_timeout(engine, proj, timeout=300):
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
    worker.join(timeout=timeout)

    if worker.is_alive():
        worker.kill()
        worker.join(5)
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

    try:
        status, data = result_queue.get_nowait()
    except Exception:
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

    projects = select_projects(db, args.min_risk, args.limit)
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

    date_str = run_start.strftime("%Y-%m-%d")
    bundles_dir = REPORT_DIR / "bundles" / date_str
    bundles_dir.mkdir(parents=True, exist_ok=True)

    # Crash-resume: load progress from any interrupted run tonight
    progress_path = REPORT_DIR / f".progress_{date_str}.json"
    completed_ids: set[str] = set()
    if progress_path.exists():
        try:
            completed_ids = set(json.loads(progress_path.read_text(encoding="utf-8")).keys())
            print(f"Resuming: {len(completed_ids)} projects already verified tonight")
        except Exception:
            pass

    # Hash-skip: load only the most recent date's bundles (not all historical)
    yesterday_bundles: dict[str, dict] = {}
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
        bundle = _verify_with_timeout(engine, proj, timeout=300)
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
        elif verdict in ("PASS", "SKIP"):
            # Single-witness pass (arbitrator returned PASS because only 1 non-skip witness)
            single_pass += 1

        # Update Q-router (success = CERTIFIED or PASS)
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

        # Save memory for non-certified projects only
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

    # Write JSON report
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = REPORT_DIR / f"nightly_{date_str}.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Write Markdown report
    md_path = REPORT_DIR / f"nightly_{date_str}.md"
    md_lines = [
        f"# Nightly Verification Report - {date_str}",
        "",
        f"**{certified}/{n + skipped_cached} CERTIFIED** ({skipped_cached} cached) | {failed} FAIL | {rejected} REJECT | {single_pass} single-witness (PASS)",
        "",
        "```mermaid",
        "pie title Nightly Verdicts",
    ]
    if certified:
        md_lines.append(f'    "CERTIFIED" : {certified}')
    if single_pass:
        md_lines.append(f'    "PASS" : {single_pass}')
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
    print(f"  {certified}/{n} CERTIFIED | {failed} FAIL | {rejected} REJECT | {single_pass} PASS")
    print(f"  Total time: {total_time:.0f}s")
    print(f"  Report: {md_path}")
    print(f"  Bundles: {bundles_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
