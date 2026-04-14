"""Tests for meta-verification canary and filesystem watcher."""
from __future__ import annotations

import time
from pathlib import Path

from overmind.activation.fs_watcher import (
    FileSystemWatcher,
    _fingerprint_project,
)
from overmind.storage.models import ProjectRecord
from overmind.verification.meta_verification import (
    build_canary_project,
    run_meta_verification,
    write_meta_verification_alarm,
    CANARY_PROJECT_ID,
)


# ── Meta-verification canary ──────────────────────────────────────


def test_build_canary_project_creates_all_required_files(tmp_path):
    project = build_canary_project(tmp_path)
    assert project.project_id == CANARY_PROJECT_ID
    assert (tmp_path / "canary_module" / "__init__.py").exists()
    assert (tmp_path / "tests" / "test_canary.py").exists()
    assert project.test_commands


def test_meta_verification_certifies_healthy_canary(tmp_path):
    result = run_meta_verification(
        canary_root=tmp_path / "canary",
        baselines_dir=tmp_path / "baselines",
    )
    # The canary should reach CERTIFIED on any healthy box. If it doesn't,
    # we've broken the verifier itself — exactly what this witness exists to catch.
    assert result.verdict in {"CERTIFIED", "PASS"}  # PASS if only 1 witness ran (tier 2)
    assert result.passed is True or result.verdict == "PASS"


def test_write_meta_verification_alarm_creates_tracked_file(tmp_path):
    from overmind.verification.meta_verification import MetaVerificationResult
    result = MetaVerificationResult(
        passed=False, verdict="FAIL", failure_class="unknown",
        reason="canary regressed", bundle_hash="deadbeef",
    )
    alarm = write_meta_verification_alarm(tmp_path, result)
    assert alarm.exists()
    assert "meta_verification_alarm" in alarm.name


# ── Filesystem watcher ────────────────────────────────────────────


def test_fingerprint_stable_across_no_change(tmp_path):
    (tmp_path / "a.py").write_text("VALUE = 1\n", encoding="utf-8")
    snap1 = _fingerprint_project(tmp_path)
    snap2 = _fingerprint_project(tmp_path)
    assert snap1 is not None and snap2 is not None
    assert snap1.fingerprint == snap2.fingerprint


def test_fingerprint_changes_when_file_changes(tmp_path):
    target = tmp_path / "a.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")
    snap1 = _fingerprint_project(tmp_path)
    time.sleep(0.02)
    target.write_text("VALUE = 2\n", encoding="utf-8")
    snap2 = _fingerprint_project(tmp_path)
    assert snap1 is not None and snap2 is not None
    assert snap1.fingerprint != snap2.fingerprint


def test_fingerprint_ignores_build_artifacts(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    snap1 = _fingerprint_project(tmp_path)

    pycache = tmp_path / "__pycache__"
    pycache.mkdir()
    (pycache / "a.cpython-313.pyc").write_bytes(b"\x00\x01")
    snap2 = _fingerprint_project(tmp_path)

    assert snap1 is not None and snap2 is not None
    assert snap1.fingerprint == snap2.fingerprint  # pycache change shouldn't affect it


def test_watcher_fires_callback_on_first_change(tmp_path):
    project_root = tmp_path / "proj"
    project_root.mkdir()
    (project_root / "main.py").write_text("x = 1\n", encoding="utf-8")

    project = ProjectRecord(
        project_id="p1", name="p1", root_path=str(project_root),
    )
    fired: list[str] = []

    watcher = FileSystemWatcher(
        projects_fn=lambda: [project],
        changed_callback=lambda pid: fired.append(pid),
        interval_seconds=0.01,
    )

    watcher.tick()  # first tick: record baseline, no fire
    assert fired == []

    time.sleep(0.02)
    (project_root / "main.py").write_text("x = 2\n", encoding="utf-8")
    watcher.tick()  # second tick: fingerprint changed, fires
    assert fired == ["p1"]


def test_watcher_swallows_callback_errors(tmp_path):
    project_root = tmp_path / "proj"
    project_root.mkdir()
    (project_root / "main.py").write_text("x = 1\n", encoding="utf-8")
    project = ProjectRecord(project_id="p1", name="p1", root_path=str(project_root))

    def broken_callback(pid: str) -> None:
        raise RuntimeError("callback blew up")

    watcher = FileSystemWatcher(
        projects_fn=lambda: [project],
        changed_callback=broken_callback,
        interval_seconds=0.01,
    )
    watcher.tick()  # baseline
    time.sleep(0.02)
    (project_root / "main.py").write_text("x = 2\n", encoding="utf-8")
    # Must not propagate.
    fired = watcher.tick()
    assert fired == []  # callback raised, so not recorded in fired list
