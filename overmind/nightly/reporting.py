"""Report-write helpers extracted from scripts/nightly_verify.py.

These were inline functions in the 1655-LOC monolith. Moving them here
shrinks the script's surface and gives them a stable import target.
Behavior is unchanged.
"""
from __future__ import annotations

import argparse
import json
import os as _os
import re
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path

from .paths import REPORT_DIR

# P2-4 (review-findings 2026-05-06 Security): scrub user-home paths from
# crash/log output before writing to disk. Tracebacks routinely include
# Windows user-profile paths which are fine on the author's machine but
# leak if logs are shared, shipped, or pasted into a bug report.
_HOME_SCRUB_RE = re.compile(r"[A-Z]:\\Users\\[^\\\s\"']+", re.IGNORECASE)


def _scrub_user_paths(text: str) -> str:
    """Replace `C:\\Users\\<username>` with `<home>` for log/diagnostic output."""
    return _HOME_SCRUB_RE.sub(r"<home>", text)


def _atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Atomic write via temp-file + os.replace.

    Per the 8-persona blinded review (P0-5 Concurrency): `Path.write_text`
    is non-atomic on Windows. Two simultaneous nightly invocations
    (manual rerun + scheduler, or two manual reruns) tearing-write the
    same `.progress_<date>.json` / `nightly_<date>.json` / per-project
    bundle JSON corrupts the file. The next iteration's `json.loads`
    raises, falls into the bare-except, and silently regresses to {}
    or {"partial": True} — defeating the don't-clobber-canonical
    invariant.

    `os.replace` is atomic on NTFS for same-volume renames (and on POSIX
    via rename(2)), so a reader sees either the old file or the new file,
    never a half-written state.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding=encoding)
    _os.replace(tmp, path)


def _promote_progress_to_partial_report(
    date_str: str,
    report_dir: Path | None = None,
    atomic_write=None,
) -> None:
    """Synthesize nightly_<date>.json from .progress_<date>.json + bundles/<date>/.

    Defensive fix per lessons.md 2026-04-30: the 14400s faulthandler safety-net
    at module top calls `_exit()` which bypasses both `finally:` blocks and
    `atexit` handlers. So a one-shot end-of-run write loses the night's verdict
    if any single project hangs past the script wall-clock cap. Instead, we
    re-promote `.progress` → partial nightly report after every project AND
    via atexit (covers exception paths even when faulthandler does not fire).

    Invariants:
      - never overwrites a non-partial report (idempotent on full success;
        the normal end-of-run write at line ~1144 produces the canonical file
        without `partial: true` and this helper refuses to clobber it)
      - never raises (atexit and per-iteration callers must not abort the run)
    """
    rd = report_dir if report_dir is not None else REPORT_DIR
    aw = atomic_write if atomic_write is not None else _atomic_write_text
    try:
        json_path = rd / f"nightly_{date_str}.json"
        if json_path.exists():
            try:
                existing = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                existing = {"partial": True}
            if not existing.get("partial"):
                return
        progress_path = rd / f".progress_{date_str}.json"
        if not progress_path.exists():
            return
        try:
            progress = json.loads(progress_path.read_text(encoding="utf-8"))
        except Exception:
            return
        tally = Counter(progress.values())
        bundles_dir = rd / "bundles" / date_str
        proj_records = []
        if bundles_dir.is_dir():
            for bundle_file in bundles_dir.glob("*.json"):
                try:
                    b = json.loads(bundle_file.read_text(encoding="utf-8"))
                    proj_records.append({
                        "name": b.get("project_id", bundle_file.stem),
                        "verdict": b.get("verdict", "?"),
                        "bundle_hash": b.get("bundle_hash", ""),
                        "arbitration_reason": b.get("arbitration_reason", ""),
                    })
                except Exception:
                    continue
        report = {
            "timestamp": datetime.now(UTC).isoformat(),
            "partial": True,
            "partial_reason": (
                "atexit / per-iteration flush — main loop did not reach the "
                "canonical end-of-run report write. See .progress_<date>.json "
                "for raw verdict map."
            ),
            "total_projects": len(progress),
            "certified": tally.get("CERTIFIED", 0),
            "rejected": tally.get("REJECT", 0),
            "failed": tally.get("FAIL", 0),
            "single_pass": tally.get("PASS", 0),
            "unverified": tally.get("UNVERIFIED", 0),
            "projects": proj_records,
        }
        rd.mkdir(parents=True, exist_ok=True)
        aw(json_path, json.dumps(report, indent=2))
    except Exception as _exc:
        try:
            crash_path = rd / f"crash_{date_str}.log"
            rd.mkdir(parents=True, exist_ok=True)
            with crash_path.open("a", encoding="utf-8") as _fh:
                _fh.write(_scrub_user_paths(
                    f"[{datetime.now(UTC).isoformat()}] "
                    f"_promote_progress_to_partial_report({date_str}) "
                    f"swallowed {type(_exc).__name__}: {_exc!s}\n"
                ))
        except Exception:
            pass


def _existing_path_arg(value: str) -> Path:
    """argparse type for --projects-from-file: must be a real, existing file.

    Rejects bare `-` (a stdin sentinel some tools accept but this script
    does not) and any path that does not resolve to a regular file. Past
    incident (2026-05-05/06): `--projects-from-file -` slipped past
    parse_args() and crashed mid-run inside _run_verification(), AFTER
    atexit and the nightly_started_<date>.flag had already been written.
    Failing here is clean: argparse exits with code 2, no crash log spam,
    no half-initialised state.
    """
    if value == "-":
        raise argparse.ArgumentTypeError(
            "'-' is not a supported file path. Pass an explicit path to a "
            "newline-separated list of project roots (stdin is not supported)."
        )
    p = Path(value)
    if not p.is_file():
        raise argparse.ArgumentTypeError(
            f"file not found: {value}. Pass a path to an existing "
            "newline-separated list of project roots."
        )
    return p


def _report_paths(report_dir: Path, date_str: str, run_start: datetime,
                  is_rerun: bool) -> tuple[Path, Path, Path | None]:
    """Decide where end-of-run report artifacts go.

    Scheduled-nightly mode (is_rerun=False): canonical paths
        nightly_<date>.json, nightly_<date>.md, latest.json.

    Rerun mode (is_rerun=True, set when --projects-from-file is passed):
        rerun_<date>_<HHMMSS>.json, rerun_<date>_<HHMMSS>.md, and None for
        latest. Past incident (2026-05-05/06): manual --projects-from-file
        invocations were overwriting nightly_<date>.json with single-project
        bodies, masking the real scheduled run (whose 48 bundle files were
        sitting next door in bundles/<date>/). The morning watchdog
        explicitly predicts this in morning_watchdog.py:130-138.
        Latest.json is intentionally None in rerun mode so the dashboard's
        "latest" pointer keeps tracking the scheduled run.
    """
    if is_rerun:
        stamp = run_start.strftime("%Y-%m-%d_%H%M%S")
        return (
            report_dir / f"rerun_{stamp}.json",
            report_dir / f"rerun_{stamp}.md",
            None,
        )
    return (
        report_dir / f"nightly_{date_str}.json",
        report_dir / f"nightly_{date_str}.md",
        report_dir / "latest.json",
    )
