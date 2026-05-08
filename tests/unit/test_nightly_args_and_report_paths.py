"""Argparse validation + rerun report-path isolation for nightly_verify.py.

Two bugs surfaced by the 2026-05-05/06 outage:

1. parse_args() accepted `--projects-from-file -` (and any non-existent
   path). The script then crashed inside _run_verification() with
   FileNotFoundError after atexit + progress-flag had already been
   registered, leaving partial state and crash logs. Fix: validate at
   parse time.

2. Manual `--projects-from-file foo.txt` reruns wrote
   nightly_<date>.json / .md / latest.json — the same paths the
   scheduled nightly uses — clobbering the canonical report. The
   bundles/<date>/ directory still showed the real scheduled run
   (e.g. 2026-05-05 had 48 bundles) but the canonical JSON reported
   total_projects: 1. morning_watchdog.py:130-138 literally predicts
   this failure mode in its alert text. Fix: reroute rerun output to
   rerun_<date>_<HHMMSS>.* and skip the latest.json overwrite.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import nightly_verify  # noqa: E402


# ---------------------------------------------------------------------------
# Bug A — argparse must reject `-` and missing files BEFORE main() runs.
# ---------------------------------------------------------------------------

def test_parse_args_rejects_dash_as_projects_from_file(monkeypatch, capsys):
    """`--projects-from-file -` must fail at parse time, not mid-run.

    Past failure: bare `-` fell through parse_args() and reached
    load_paths_filter() in _run_verification(), which raised
    FileNotFoundError after atexit hooks were already registered.
    """
    monkeypatch.setattr(sys, "argv", ["nightly_verify.py", "--projects-from-file", "-"])
    with pytest.raises(SystemExit) as excinfo:
        nightly_verify.parse_args()
    # argparse exits with code 2 on argument errors
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "--projects-from-file" in err


def test_parse_args_rejects_nonexistent_file(monkeypatch, capsys, tmp_path):
    """A typoed path must fail at parse time with a clear message."""
    missing = tmp_path / "does_not_exist.txt"
    monkeypatch.setattr(sys, "argv", ["nightly_verify.py", "--projects-from-file", str(missing)])
    with pytest.raises(SystemExit) as excinfo:
        nightly_verify.parse_args()
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "--projects-from-file" in err


def test_parse_args_accepts_real_file(monkeypatch, tmp_path):
    """A valid path-list file must parse cleanly."""
    f = tmp_path / "paths.txt"
    f.write_text("# header\nC:/Models/Alpha\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["nightly_verify.py", "--projects-from-file", str(f)])
    args = nightly_verify.parse_args()
    assert args.projects_from_file == f


def test_parse_args_no_projects_from_file_keeps_default(monkeypatch):
    """Default scheduled-nightly invocation must continue to parse."""
    monkeypatch.setattr(sys, "argv", ["nightly_verify.py", "--limit", "50"])
    args = nightly_verify.parse_args()
    assert args.projects_from_file is None
    assert args.limit == 50


# ---------------------------------------------------------------------------
# Bug B — rerun mode must not clobber canonical nightly artifacts.
# ---------------------------------------------------------------------------

def test_report_paths_scheduled_mode_uses_canonical_nightly_filenames(tmp_path):
    """Default mode (no --projects-from-file) writes nightly_<date>.* + latest.json."""
    run_start = datetime(2026, 5, 7, 11, 0, 0, tzinfo=timezone.utc)
    json_path, md_path, latest_path = nightly_verify._report_paths(
        tmp_path, "2026-05-07", run_start, is_rerun=False,
    )
    assert json_path == tmp_path / "nightly_2026-05-07.json"
    assert md_path == tmp_path / "nightly_2026-05-07.md"
    assert latest_path == tmp_path / "latest.json"


def test_report_paths_rerun_mode_uses_rerun_filenames(tmp_path):
    """Rerun mode writes rerun_<date>_<HHMMSS>.* and skips latest.json."""
    run_start = datetime(2026, 5, 7, 14, 32, 11, tzinfo=timezone.utc)
    json_path, md_path, latest_path = nightly_verify._report_paths(
        tmp_path, "2026-05-07", run_start, is_rerun=True,
    )
    # Rerun filenames embed the wall-clock so multiple reruns on the same
    # day don't overwrite each other.
    assert json_path == tmp_path / "rerun_2026-05-07_143211.json"
    assert md_path == tmp_path / "rerun_2026-05-07_143211.md"
    # latest.json is skipped in rerun mode — the dashboard's "latest"
    # pointer must keep tracking the scheduled run.
    assert latest_path is None


def test_report_paths_rerun_does_not_clobber_scheduled_artifacts(tmp_path):
    """A rerun on the same date as a scheduled run leaves the canonical files alone."""
    # Simulate a scheduled run that already wrote the canonical report
    canonical_json = tmp_path / "nightly_2026-05-07.json"
    canonical_md = tmp_path / "nightly_2026-05-07.md"
    canonical_latest = tmp_path / "latest.json"
    canonical_json.write_text('{"total_projects": 48}', encoding="utf-8")
    canonical_md.write_text("# Canonical run\n", encoding="utf-8")
    canonical_latest.write_text('{"total_projects": 48}', encoding="utf-8")

    run_start = datetime(2026, 5, 7, 14, 32, 11, tzinfo=timezone.utc)
    json_path, md_path, latest_path = nightly_verify._report_paths(
        tmp_path, "2026-05-07", run_start, is_rerun=True,
    )
    # Paths returned are rerun_*, not the canonical ones
    assert json_path != canonical_json
    assert md_path != canonical_md
    assert latest_path is None
    # And the canonical files are still intact and unmodified
    assert canonical_json.read_text(encoding="utf-8") == '{"total_projects": 48}'
    assert canonical_md.read_text(encoding="utf-8") == "# Canonical run\n"
    assert canonical_latest.read_text(encoding="utf-8") == '{"total_projects": 48}'
