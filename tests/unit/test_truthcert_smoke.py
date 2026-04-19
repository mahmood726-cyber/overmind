from __future__ import annotations

import subprocess
from pathlib import Path

from overmind.storage.models import ProjectRecord
from overmind.verification.truthcert_engine import TruthCertEngine
from overmind.verification.witnesses import SmokeWitness, SuiteWitness


def test_truthcert_engine_discovers_src_python_and_js_targets(tmp_path):
    project_root = tmp_path / "demo"
    src_pkg = project_root / "src" / "evidencekit"
    ui_dir = project_root / "ui"
    src_pkg.mkdir(parents=True)
    ui_dir.mkdir(parents=True)

    (src_pkg / "__init__.py").write_text("from .model import VALUE\n", encoding="utf-8")
    (src_pkg / "model.py").write_text("VALUE = 1\n", encoding="utf-8")
    (project_root / "analysis.py").write_text("VALUE = 2\n", encoding="utf-8")
    (project_root / "app.js").write_text("const x = 1;\n", encoding="utf-8")
    (ui_dir / "dashboard.js").write_text("const y = 2;\n", encoding="utf-8")

    engine = TruthCertEngine(tmp_path / "baselines")
    targets = engine._discover_modules(str(project_root))

    assert "py:analysis" in targets
    assert "py:evidencekit" in targets
    assert "py:evidencekit.model" in targets
    assert "js:app.js" in targets
    assert "js:ui/dashboard.js" in targets


def test_smoke_witness_imports_src_layout_module(tmp_path):
    project_root = tmp_path / "demo"
    src_pkg = project_root / "src" / "evidencekit"
    src_pkg.mkdir(parents=True)
    (src_pkg / "model.py").write_text("VALUE = 1\n", encoding="utf-8")

    result = SmokeWitness(timeout=5).run(["py:evidencekit.model"], str(project_root))

    assert result.verdict == "PASS"
    assert result.stdout == "1 modules imported OK"


def test_smoke_witness_runs_node_check_for_js_targets(tmp_path, monkeypatch):
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = SmokeWitness(timeout=5).run(["js:app.js"], str(tmp_path))

    assert result.verdict == "PASS"
    assert calls == [["node", "--check", "app.js"]]


def test_truthcert_scope_lock_uses_smoke_targets_for_medium_high_project(tmp_path):
    project_root = tmp_path / "demo"
    project_root.mkdir()
    (project_root / "analysis.py").write_text("VALUE = 1\n", encoding="utf-8")

    project = ProjectRecord(
        project_id="demo-project",
        name="demo-project",
        root_path=str(project_root),
        project_type="python_tool",
        stack=["python"],
        risk_profile="medium_high",
    )

    engine = TruthCertEngine(tmp_path / "baselines")
    lock = engine.build_scope_lock(project)

    assert lock.witness_count == 2
    assert "py:analysis" in lock.smoke_modules


def test_truthcert_engine_discovers_nested_python_packages(tmp_path):
    project_root = tmp_path / "demo"
    nested_pkg = project_root / "src" / "evidencekit" / "subpkg"
    nested_pkg.mkdir(parents=True)

    (nested_pkg.parent / "__init__.py").write_text("", encoding="utf-8")
    (nested_pkg / "__init__.py").write_text("", encoding="utf-8")
    (nested_pkg / "module.py").write_text("VALUE = 1\n", encoding="utf-8")

    engine = TruthCertEngine(tmp_path / "baselines")
    targets = engine._discover_modules(str(project_root))

    assert "py:evidencekit" in targets
    assert "py:evidencekit.subpkg" in targets
    assert "py:evidencekit.subpkg.module" in targets


def test_truthcert_discover_skips_build_and_dist_artifact_dirs(tmp_path):
    """`build/` and `dist/` are PEP-517 / setuptools output directories — they
    contain copies of the source tree that shadow the real package. Smoke
    witness tried to import them as `build.lib.<pkg>.…` which always fails
    with ModuleNotFoundError. Regression for advanced-nma-pooling (2026-04-16)
    where a stale `build/lib/nma_pool/` tree from a previous editable install
    caused smoke to FAIL every run."""
    project_root = tmp_path / "demo"
    # Real source
    (project_root / "src" / "nma_pool").mkdir(parents=True)
    (project_root / "src" / "nma_pool" / "__init__.py").write_text("", encoding="utf-8")
    (project_root / "src" / "nma_pool" / "core.py").write_text("VALUE = 1\n", encoding="utf-8")
    # Stale build/ artifact that mirrors the source
    (project_root / "build" / "lib" / "nma_pool").mkdir(parents=True)
    (project_root / "build" / "lib" / "nma_pool" / "__init__.py").write_text("", encoding="utf-8")
    (project_root / "build" / "lib" / "nma_pool" / "core.py").write_text("VALUE = 1\n", encoding="utf-8")
    # dist/ artifact (wheel or tarball contents unpacked)
    (project_root / "dist" / "pkg").mkdir(parents=True)
    (project_root / "dist" / "pkg" / "__init__.py").write_text("", encoding="utf-8")

    engine = TruthCertEngine(tmp_path / "baselines")
    targets = engine._discover_modules(str(project_root))

    # Real source discovered
    assert "py:nma_pool" in targets
    assert "py:nma_pool.core" in targets
    # Build/dist artifacts skipped — these would fail to import anyway
    for t in targets:
        assert "build.lib" not in t, f"build/ artifact leaked into smoke modules: {t}"
        assert not t.startswith("py:dist."), f"dist/ artifact leaked into smoke modules: {t}"


def test_truthcert_source_hash_changes_for_nested_source_file(tmp_path):
    project_root = tmp_path / "demo"
    nested_pkg = project_root / "pkg" / "subpkg"
    nested_pkg.mkdir(parents=True)
    target = nested_pkg / "module.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")

    engine = TruthCertEngine(tmp_path / "baselines")
    hash_before = engine._hash_source_files(str(project_root))

    target.write_text("VALUE = 2\n", encoding="utf-8")
    hash_after = engine._hash_source_files(str(project_root))

    assert hash_before != hash_after


def test_truthcert_source_hash_survives_oserror_during_walk(tmp_path, monkeypatch):
    """P1-6: `os.walk` mid-iteration errors (reparse points, OneDrive
    placeholders) must not abort the hash pass — the onerror handler should
    skip the unreadable subtree."""
    import os as _os

    project_root = tmp_path / "demo"
    project_root.mkdir()
    (project_root / "ok.py").write_text("VALUE = 1\n", encoding="utf-8")

    real_walk = _os.walk

    def flaky_walk(top, *args, **kwargs):
        onerror = kwargs.get("onerror")
        if args:
            onerror = args[0] if args[0] is not None else onerror
        # Simulate scandir raising partway through; the verifier's handler
        # should swallow this and continue.
        if onerror is not None:
            onerror(OSError(1920, "simulated reparse-point failure"))
        yield from real_walk(top, *args, **kwargs)

    monkeypatch.setattr(_os, "walk", flaky_walk)

    engine = TruthCertEngine(tmp_path / "baselines")
    result = engine._hash_source_files(str(project_root))

    assert isinstance(result, str) and len(result) == 16


def test_truthcert_source_hash_skips_inaccessible_paths(tmp_path, monkeypatch):
    """Nightly crash repro: .venv/lib64 symlink raises OSError on is_file().

    Regression for WinError 1920 crash at 2026-04-14 where a OneDrive-hosted
    .venv/lib64 symlink aborted the entire scope-lock build.
    """
    project_root = tmp_path / "demo"
    project_root.mkdir()
    (project_root / "analysis.py").write_text("VALUE = 1\n", encoding="utf-8")

    venv = project_root / ".venv"
    venv.mkdir()
    poison = venv / "lib64"
    poison.write_text("placeholder\n", encoding="utf-8")

    # Patch at os.stat rather than Path.is_file. `Path.is_file` internally
    # calls os.stat(self, follow_symlinks=True). os.stat has accepted the
    # follow_symlinks kwarg since Python 3.3, while Path.is_file only
    # accepted it from 3.13 onward — patching there broke the test on
    # 3.11/3.12 runners.
    import os
    real_stat = os.stat

    def flaky_stat(path, *, follow_symlinks=True):
        path_str = os.fspath(path)
        # Match the OneDrive placeholder that caused WinError 1920:
        # a "lib64" file inside a .venv directory.
        sep = os.sep
        needle = f"{sep}.venv{sep}lib64"
        if path_str.endswith(needle) or path_str.endswith(".venv/lib64"):
            raise OSError(1920, "The file cannot be accessed by the system")
        return real_stat(path, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(os, "stat", flaky_stat)

    engine = TruthCertEngine(tmp_path / "baselines")
    result = engine._hash_source_files(str(project_root))

    assert isinstance(result, str) and len(result) == 16


def test_suite_witness_handles_non_ascii_subprocess_output(tmp_path):
    """Regression 2026-04-16: SuiteWitness crashed with
    `TypeError: 'NoneType' object is not subscriptable` when a test-command
    subprocess (e.g. Rscript with testthat progress glyphs) emits bytes
    that cp1252 can't decode. Root cause: `text=True` without an explicit
    `encoding=` defaults to locale (cp1252 on Windows), and the reader
    thread dies → proc.stdout/stderr become None.

    Fix is to pass encoding='utf-8', errors='replace' consistently with
    the other subprocess.run calls in this file."""
    import sys
    # Minimal reproducer: a Python one-liner that emits a non-ASCII glyph
    # similar to what testthat spinners write (✔ / ✖ / ⠏ etc.)
    script = tmp_path / "emit.py"
    # cp1252 has undefined positions 0x81, 0x8D, 0x8F, 0x90, 0x9D — emitting
    # any of these bytes to stdout while subprocess.run uses text=True with
    # cp1252 default triggers the reader-thread crash that zeroes stdout/stderr.
    script.write_text(
        'import sys\n'
        'sys.stdout.buffer.write(b"test output with cp1252-undefined byte: \\x8f\\n")\n'
        'sys.stdout.buffer.flush()\n',
        encoding="utf-8",
    )
    command = f'"{sys.executable}" "{script}"'

    result = SuiteWitness(timeout=30).run(command, str(tmp_path))

    # Must not crash. Verdict is PASS (exit 0) and stdout/stderr are strings.
    assert result.verdict == "PASS", f"expected PASS, got {result.verdict!r}; stderr={result.stderr!r}"
    assert isinstance(result.stdout, str)
    assert isinstance(result.stderr, str)


def test_suite_witness_blocks_unsafe_wrapper_command(tmp_path):
    script = tmp_path / "safe.cmd"
    script.write_text("@echo off\r\necho ok\r\n", encoding="utf-8")

    result = SuiteWitness(timeout=5).run(
        f'cmd /c "{script}" && del /s /q C:\\*',
        str(tmp_path),
    )

    assert result.verdict == "FAIL"
    assert "unsafe shell control operator" in result.stderr
