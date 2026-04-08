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
        faulthandler.dump_traceback_later(300, exit=True)  # safety net: kill if hung >5min
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


def _verdict_symbol(verdict: str) -> str:
    return {
        "CERTIFIED": "CERTIFIED",
        "REJECT": "REJECT",
        "FAIL": "FAIL",
        "PASS": "PASS",
        "SKIP": "SKIP",
    }.get(verdict, verdict)


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
        db.close()
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

    for i, proj in enumerate(projects, 1):
        print(f"[{i}/{len(projects)}] {proj.name}...", end=" ", flush=True)
        start = time.time()
        bundle = engine.verify(proj)
        elapsed = time.time() - start

        results.append({"project": proj, "bundle": bundle, "elapsed": elapsed})

        verdict = bundle.verdict
        symbol = _verdict_symbol(verdict)
        print(f"{symbol} ({elapsed:.1f}s) [{bundle.arbitration_reason}]")

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

    # Dream cycle
    print()
    print("Dreaming...", end=" ", flush=True)
    dream = dream_engine.dream()
    print(f"done ({dream['merges']} merges, {dream['archives']} archives)")

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
        f"**{certified}/{n} CERTIFIED** | {failed} FAIL | {rejected} REJECT | {single_pass} single-witness (PASS)",
        "",
    ]

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

    db.close()


if __name__ == "__main__":
    main()
