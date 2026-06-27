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
import os
import platform
import re
import sys
import time
from collections import Counter
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
        # Safety net: kill if the WHOLE script hangs >4 hours. Was 1 hour
        # but per-project --worker-timeout can be 3600s (rct-extractor-v2,
        # evidence-inference) and a targeted run with 3 such projects
        # would exceed 1 hour even when each project succeeds. 4 hours
        # is still a reasonable upper bound for a single targeted run.
        # P1-9 (review-findings 2026-05-06): redirect faulthandler output to
        # a persistent file so the 2026-05-04-style _exit() failure mode
        # leaves a forensic trail. Stderr alone is lost when Task Scheduler
        # has no console to flush to.
        try:
            _fh_log_dir = Path(__file__).resolve().parents[1] / "data" / "nightly_reports"
            _fh_log_dir.mkdir(parents=True, exist_ok=True)
            _fh_log = open(
                _fh_log_dir / f"faulthandler_{datetime.now(UTC).strftime('%Y-%m-%d')}.log",
                "a", encoding="utf-8",
            )
            faulthandler.enable(file=_fh_log)
        except Exception:
            faulthandler.enable()  # fallback to stderr
        faulthandler.dump_traceback_later(14400, exit=True)
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

# Phase-3 M: extracted helpers now live in `overmind.nightly.*`. The
# imports below re-export the same names this module previously defined
# inline, so test fixtures and downstream code that reach for
# `nightly_verify.SKIP_PROJECTS` / `nightly_verify.select_projects` /
# `nightly_verify._report_paths` etc. continue to resolve.
from overmind.nightly.paths import DATA_DIR, DB_PATH, REPORT_DIR  # noqa: E402,F401
from overmind.nightly.selection import (  # noqa: E402,F401
    SKIP_PROJECTS,
    PROJECT_WORKER_TIMEOUTS,
    _normalize_path,
    load_paths_filter,
    select_projects,
)
from overmind.nightly.reporting import (  # noqa: E402,F401
    _atomic_write_text,
    _promote_progress_to_partial_report as _promote_impl,
    _scrub_user_paths,
    _existing_path_arg,
    _report_paths,
)


def _promote_progress_to_partial_report(date_str: str) -> None:
    """Thin wrapper that lets pytest fixtures monkeypatch this module's
    REPORT_DIR and _atomic_write_text and have those overrides flow into
    the extracted helper. Without this, the helper would resolve those
    names against `overmind.nightly.reporting`, not the test's monkey-
    patched targets on nightly_verify itself."""
    _promote_impl(date_str, report_dir=REPORT_DIR, atomic_write=_atomic_write_text)
from overmind.nightly.integrations import (  # noqa: E402,F401
    collect_sentinel_findings,
    _run_portfolio_sentinel_scan,
    collect_bypass_findings,
)


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
    parser.add_argument("--projects-from-file", type=_existing_path_arg, default=None, metavar="PATH",
                        help="File of project paths (one per line) to verify. Bypasses "
                             "--min-risk and --limit so an operator can re-bundle a "
                             "specific set of paths (e.g. stale-UNVERIFIED projects) "
                             "without waiting for the natural risk-sorted cadence. "
                             "Lines starting with '#' and blank lines are ignored. "
                             "When set, the report is written to rerun_<date>_<HHMMSS>.json "
                             "instead of nightly_<date>.json so manual reruns do not "
                             "clobber the canonical scheduled-nightly artifact.")
    # QW-2: USD budget ceiling for the LLM repair/upgrade phase
    parser.add_argument("--budget-usd", type=float, default=None, metavar="FLOAT",
                        help="Halt LLM repair/upgrade calls when cumulative estimated "
                             "spend reaches this ceiling (USD). Does not stop the whole "
                             "run — only the LLM phase. Required when --loop-mode is set.")
    # QW-2: loop mode (requires --budget-usd; enforced below)
    parser.add_argument("--loop-mode", action="store_true",
                        help="Re-invoke the verification pass up to max_iterations while "
                             "goal not met. Requires --budget-usd to guard spend.")
    # QW-4: bypass SAFE_FIX_ACTIONS allowlist (default: restricted to safe types)
    parser.add_argument("--unsafe-fixes", action="store_true",
                        help="Bypass the SAFE_FIX_ACTIONS allowlist and allow all "
                             "auto-fix types (default: only BASELINE_UPDATE / "
                             "FLOAT_PRECISION / FORMULA_ERROR are attempted).")
    # QW-5: mark this as a human-initiated manual run (sets verified_in_manual_run
    # on promoted recipes, required by PromotionGate when manual_run_required=True)
    parser.add_argument("--manual", action="store_true",
                        help="Mark this as a manually-triggered run. Recipes resolved "
                             "in a manual run satisfy the manual_run_required gate in "
                             "PromotionGate.")
    args = parser.parse_args()
    # QW-2: loop-mode requires an explicit budget ceiling
    if args.loop_mode and args.budget_usd is None:
        parser.error("--loop-mode requires --budget-usd (e.g. --budget-usd 1.0) "
                     "to guard against unbounded spend")
    return args


# Phase-4 M-2: heavy verification driver moved to overmind.nightly.runner.
# Re-export the public surface so test fixtures and Sentinel scripts that
# look up `nightly_verify._verify_with_timeout` / `_run_verification` etc.
# continue to resolve. Functions are unmodified — they just live in a
# different file now.
from overmind.nightly.runner import (  # noqa: E402,F401
    _verify_worker,
    _verify_with_timeout,
    _load_last_night_diagnoses,
    _run_verification,
)


def main() -> None:
    args = parse_args()
    run_start = datetime.now(UTC)
    print(f"Overmind Nightly Verifier - {run_start.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Config: limit={args.limit}, timeout={args.timeout}s, min_risk={args.min_risk}, dry_run={args.dry_run}")
    print()

    # Register atexit promote-to-partial. Covers normal exit and unhandled-
    # exception paths. Does NOT cover faulthandler.exit=True (which uses
    # os._exit and bypasses atexit) — for that case the per-iteration call
    # inside the verification loop is the safety net.
    import atexit
    atexit.register(_promote_progress_to_partial_report, run_start.strftime("%Y-%m-%d"))

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
        crash_path = REPORT_DIR / f"crash_{run_start.strftime('%Y-%m-%d')}.log"
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        crash_path.write_text(
            _scrub_user_paths(
                f"Nightly crash at {datetime.now(UTC).isoformat()}\n\n{traceback.format_exc()}"
            ),
            encoding="utf-8",
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
