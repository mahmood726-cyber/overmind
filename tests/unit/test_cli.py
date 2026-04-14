from __future__ import annotations

import os
import subprocess
import sys

from overmind import cli


def test_python_module_cli_help_outputs_usage():
    proc = subprocess.run(
        [sys.executable, "-m", "overmind.cli", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
    )

    assert proc.returncode == 0
    assert "usage: overmind" in proc.stdout.lower()


class _BrokenPipeStream:
    def write(self, _text):
        raise BrokenPipeError


def test_emit_payload_handles_broken_pipe():
    exit_code = cli._emit_payload({"ok": True}, stream=_BrokenPipeStream())

    assert exit_code == 0


def test_windows_powershell_pipeline_is_quiet_on_broken_pipe(tmp_path):
    if os.name != "nt":
        return

    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir()
    data_dir.mkdir()

    command = (
        f"$null = & '{sys.executable}' -m overmind.cli "
        f"--config-dir '{config_dir}' --data-dir '{data_dir}' --db-path '{data_dir / 'state.db'}' "
        "show-state | Select-Object -First 1; exit $LASTEXITCODE"
    )
    proc = subprocess.run(
        ["powershell", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )

    assert proc.stderr == ""
    assert proc.returncode in {0, 4294967295}
