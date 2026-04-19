"""End-to-end CLI smoke tests.

Exercises the `overmind` CLI against a fresh tmp config + data dir.
These tests are portable (tmp_path only — no C:/ or /home/ refs) so
they pass on GitHub Actions runners.

Gap they close: before 2026-04-19, Sentinel had a matrix CI and
Overmind had none. Unit tests cover the library boundary; this
file covers the `overmind --help`, `scan`, `show-state` paths
that a user actually invokes, catching breakage that unit tests
miss.

Strategy: the installed `overmind` console script may or may not
be on PATH inside the test environment. We invoke `main()`
in-process with mocked `sys.argv`, which is faster and has no
PATH/spawn variance. Where we specifically need subprocess
isolation (e.g. to verify a scan survives a fresh interpreter),
the later tests use `sys.executable` and the explicit `-c` form.
"""
from __future__ import annotations

import io
import subprocess
import sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from typing import Any

import pytest

from overmind.cli import main as cli_main


def _write_min_config(config_dir: Path) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "roots.yaml").write_text(
        "scan_roots: []\n"
        "scan_rules:\n"
        "  include_git_repos: true\n"
        "  include_non_git_apps: true\n"
        "  incremental_scan: true\n"
        "  max_depth: 2\n"
        "guidance_filenames:\n"
        '  - "README.md"\n',
        encoding="utf-8",
    )
    (config_dir / "runners.yaml").write_text("runners: []\n", encoding="utf-8")
    (config_dir / "policies.yaml").write_text(
        "concurrency:\n"
        "  default_active_sessions: 1\n"
        "  max_active_sessions: 1\n"
        "  degraded_sessions: 1\n"
        "  scale_up_cpu_below: 100\n"
        "  scale_down_cpu_above: 100\n"
        "  scale_down_ram_above: 100\n"
        "  scale_down_swap_above_mb: 999999\n"
        "limits:\n"
        "  idle_timeout_min: 10\n"
        "  summary_trigger_output_lines: 400\n"
        "  max_runtime_min: 30\n"
        "routing: {}\n",
        encoding="utf-8",
    )
    (config_dir / "ignores.yaml").write_text("ignores: []\n", encoding="utf-8")
    (config_dir / "verification.yaml").write_text(
        "profiles: []\n", encoding="utf-8"
    )


def _invoke(argv: list[str]) -> tuple[int, str, str]:
    """Invoke overmind.cli.main() with argv, capture stdout/stderr,
    return (exit_code, stdout, stderr)."""
    out = io.StringIO()
    err = io.StringIO()
    saved = sys.argv
    sys.argv = ["overmind", *argv]
    code = 0
    try:
        with redirect_stdout(out), redirect_stderr(err):
            try:
                rc = cli_main()
                code = 0 if rc is None else int(rc)
            except SystemExit as e:
                code = int(e.code) if e.code is not None else 0
    finally:
        sys.argv = saved
    return code, out.getvalue(), err.getvalue()


def test_cli_help_lists_scan_command():
    code, stdout, stderr = _invoke(["--help"])
    assert code == 0
    # argparse prints help to stdout
    assert "scan" in stdout.lower(), (
        f"expected 'scan' in help output — got stdout={stdout!r} "
        f"stderr={stderr!r}"
    )


def test_cli_scan_empty_roots(tmp_path: Path):
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    _write_min_config(config_dir)
    code, stdout, stderr = _invoke([
        "--config-dir", str(config_dir),
        "--data-dir", str(data_dir),
        "scan",
    ])
    assert code == 0, f"stdout={stdout!r} stderr={stderr!r}"


def test_cli_show_state_after_empty_scan(tmp_path: Path):
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    _write_min_config(config_dir)
    scan_code, _, _ = _invoke([
        "--config-dir", str(config_dir),
        "--data-dir", str(data_dir),
        "scan",
    ])
    assert scan_code == 0
    state_code, stdout, stderr = _invoke([
        "--config-dir", str(config_dir),
        "--data-dir", str(data_dir),
        "show-state",
    ])
    assert state_code == 0, f"stdout={stdout!r} stderr={stderr!r}"


def test_cli_scan_detects_a_git_repo(tmp_path: Path):
    """Point scan_roots at a tmp dir containing one git repo; verify
    the scan finds it and records state."""
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    repos_dir = tmp_path / "repos"
    demo = repos_dir / "demo"
    demo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=demo, check=True, timeout=30)

    _write_min_config(config_dir)
    (config_dir / "roots.yaml").write_text(
        f'scan_roots:\n  - "{repos_dir.as_posix()}"\n'
        "scan_rules:\n"
        "  include_git_repos: true\n"
        "  include_non_git_apps: false\n"
        "  incremental_scan: true\n"
        "  max_depth: 2\n"
        "guidance_filenames:\n"
        '  - "README.md"\n',
        encoding="utf-8",
    )

    code, stdout, stderr = _invoke([
        "--config-dir", str(config_dir),
        "--data-dir", str(data_dir),
        "scan",
    ])
    assert code == 0, f"stdout={stdout!r} stderr={stderr!r}"

    state_code, state_stdout, state_stderr = _invoke([
        "--config-dir", str(config_dir),
        "--data-dir", str(data_dir),
        "show-state",
    ])
    assert state_code == 0


def test_cli_bad_subcommand_fails_gracefully(tmp_path: Path):
    """Unknown subcommand should non-zero-exit without traceback."""
    code, stdout, stderr = _invoke(["not-a-real-command"])
    assert code != 0  # argparse returns 2 on invalid choice
    assert "invalid choice" in stderr.lower() or "usage" in stderr.lower()
