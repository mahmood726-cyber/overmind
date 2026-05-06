"""Tests for scripts/nightly_verify._promote_progress_to_partial_report.

Per the 8-persona blinded review (P0-6 Test Coverage): the helper carries
three explicit invariants in its docstring and zero tests verified them.
This test file locks in:

1. No `.progress_<date>.json` → no-op (no nightly_<date>.json written)
2. progress + bundles present → writes partial:true with verdict tally
3. Idempotency: pre-existing canonical (non-partial) report NOT overwritten
4. Pre-existing partial report IS overwritten (newer counts)
5. Malformed progress JSON → swallowed, returns None
6. Bundles dir missing → projects:[], still writes
7. Helper never raises — even when filesystem operations themselves fail

The promote_progress helper is the safety-net that survives
faulthandler.dump_traceback_later(exit=True) which calls os._exit() and
bypasses both atexit and finally:. A regression here means an interrupted
nightly leaves no partial verdict, which silently regresses the system to
the pre-2026-05-06 failure mode (3 days of dark nights).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# Load nightly_verify.py as a module without running its main()
_NIGHTLY_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "nightly_verify.py"
)


@pytest.fixture
def promote_helper(tmp_path, monkeypatch):
    """Import the helper with REPORT_DIR pointed at tmp_path so each test
    has an isolated filesystem.
    """
    # Pre-emptively make pytest sentinel visible so the WMI-deadlock
    # monkeypatch + faulthandler.dump_traceback_later don't fire when
    # importing the script.
    sys.modules.setdefault("pytest_sentinel", type(sys)("pytest_sentinel"))
    spec = importlib.util.spec_from_file_location("nightly_verify_underTest", _NIGHTLY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    monkeypatch.setattr(mod, "REPORT_DIR", tmp_path)
    return mod


def _write_progress(report_dir: Path, date_str: str, progress: dict) -> Path:
    p = report_dir / f".progress_{date_str}.json"
    p.write_text(json.dumps(progress), encoding="utf-8")
    return p


def _write_bundle(report_dir: Path, date_str: str, project_id: str, verdict: str) -> Path:
    bdir = report_dir / "bundles" / date_str
    bdir.mkdir(parents=True, exist_ok=True)
    p = bdir / f"{project_id[:16]}.json"
    p.write_text(json.dumps({
        "project_id": project_id,
        "verdict": verdict,
        "bundle_hash": "deadbeef",
        "arbitration_reason": "test",
    }), encoding="utf-8")
    return p


def test_no_progress_file_is_noop(tmp_path, promote_helper):
    """No .progress_<date>.json on disk → helper is a no-op (no nightly_<date>.json written)."""
    promote_helper._promote_progress_to_partial_report("2099-01-01")
    assert not (tmp_path / "nightly_2099-01-01.json").exists()


def test_writes_partial_report_with_verdict_tally(tmp_path, promote_helper):
    """progress + bundles present → partial:true report with correct tally."""
    date = "2099-01-02"
    _write_progress(tmp_path, date, {
        "alpha-aaaa": "CERTIFIED",
        "beta-bbbb": "FAIL",
        "gamma-cccc": "REJECT",
        "delta-dddd": "UNVERIFIED",
        "epsilon-ee": "CERTIFIED",
    })
    _write_bundle(tmp_path, date, "alpha-aaaa", "CERTIFIED")
    _write_bundle(tmp_path, date, "beta-bbbb", "FAIL")

    promote_helper._promote_progress_to_partial_report(date)

    report = json.loads((tmp_path / f"nightly_{date}.json").read_text(encoding="utf-8"))
    assert report["partial"] is True
    assert report["total_projects"] == 5
    assert report["certified"] == 2
    assert report["failed"] == 1
    assert report["rejected"] == 1
    assert report["unverified"] == 1
    assert len(report["projects"]) == 2  # only the two with bundle JSONs


def test_idempotency_canonical_report_not_overwritten(tmp_path, promote_helper):
    """Pre-existing canonical (non-partial) report MUST NOT be regressed by helper."""
    date = "2099-01-03"
    canonical = {
        "timestamp": "2099-01-03T00:00:00Z",
        "total_projects": 50,
        "certified": 48,
        # Notably NO "partial" key — that's what makes it canonical.
    }
    (tmp_path / f"nightly_{date}.json").write_text(json.dumps(canonical), encoding="utf-8")
    _write_progress(tmp_path, date, {"alpha-aaaa": "CERTIFIED"})

    promote_helper._promote_progress_to_partial_report(date)

    after = json.loads((tmp_path / f"nightly_{date}.json").read_text(encoding="utf-8"))
    assert after == canonical, "canonical report was clobbered by partial-flush helper"


def test_pre_existing_partial_is_overwritten(tmp_path, promote_helper):
    """A stale partial:true report from earlier in the run IS replaced with newer counts."""
    date = "2099-01-04"
    stale = {"timestamp": "old", "partial": True, "total_projects": 1, "certified": 1}
    (tmp_path / f"nightly_{date}.json").write_text(json.dumps(stale), encoding="utf-8")

    _write_progress(tmp_path, date, {f"p{i}": "CERTIFIED" for i in range(5)})

    promote_helper._promote_progress_to_partial_report(date)

    after = json.loads((tmp_path / f"nightly_{date}.json").read_text(encoding="utf-8"))
    assert after["partial"] is True
    assert after["total_projects"] == 5
    assert after["certified"] == 5


def test_malformed_progress_json_swallowed(tmp_path, promote_helper):
    """Corrupt JSON in .progress_<date>.json → helper returns None, no exception."""
    date = "2099-01-05"
    (tmp_path / f".progress_{date}.json").write_text("not valid json{", encoding="utf-8")

    # Must not raise.
    promote_helper._promote_progress_to_partial_report(date)
    # And must NOT have written a nightly report from corrupt input.
    assert not (tmp_path / f"nightly_{date}.json").exists()


def test_missing_bundles_dir(tmp_path, promote_helper):
    """No bundles/<date>/ → projects: [], still writes a partial report."""
    date = "2099-01-06"
    _write_progress(tmp_path, date, {"alpha-aaaa": "CERTIFIED"})
    # Note: no _write_bundle calls.

    promote_helper._promote_progress_to_partial_report(date)

    report = json.loads((tmp_path / f"nightly_{date}.json").read_text(encoding="utf-8"))
    assert report["partial"] is True
    assert report["total_projects"] == 1
    assert report["certified"] == 1
    assert report["projects"] == []


def test_helper_never_raises_on_io_failure(tmp_path, promote_helper, monkeypatch):
    """Helper must NEVER raise — even when filesystem itself fails. Crash logged."""
    date = "2099-01-07"
    _write_progress(tmp_path, date, {"alpha-aaaa": "CERTIFIED"})

    # Force write-time failure by monkeypatching the atomic write helper.
    def _boom(path, content, encoding="utf-8"):
        raise OSError("simulated disk-full")
    monkeypatch.setattr(promote_helper, "_atomic_write_text", _boom)

    # Must NOT propagate the OSError.
    promote_helper._promote_progress_to_partial_report(date)
    # The crash log SHOULD have been written (P1-2 from review).
    crash_log = tmp_path / f"crash_{date}.log"
    assert crash_log.exists(), "exception was swallowed but not logged"
    log_content = crash_log.read_text(encoding="utf-8")
    assert "OSError" in log_content
    assert "simulated disk-full" in log_content


def test_atomic_write_text_helper(tmp_path, promote_helper):
    """The _atomic_write_text helper itself: writes via tmp+os.replace."""
    target = tmp_path / "deep" / "nested" / "out.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    promote_helper._atomic_write_text(target, '{"k": "v"}')
    assert target.read_text(encoding="utf-8") == '{"k": "v"}'
    # No leftover .tmp file
    assert not (target.with_suffix(target.suffix + ".tmp")).exists()
