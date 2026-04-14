from __future__ import annotations

import json
import sys

import overmind.subprocess_utils as subprocess_utils
from overmind.subprocess_utils import split_command, validate_command_prefix_with_detail
from overmind.verification.witnesses import NumericalWitness


def test_split_command_preserves_windows_absolute_paths():
    command = (
        r"C:\Users\user\AppData\Local\Programs\Python\Python313\python.exe "
        r"C:\overmind\data\baseline_probes\probe_truthcert-denominator.py"
    )

    parts = split_command(command)

    assert parts == [
        r"C:\Users\user\AppData\Local\Programs\Python\Python313\python.exe",
        r"C:\overmind\data\baseline_probes\probe_truthcert-denominator.py",
    ]


def test_split_command_resolves_windows_cmd_shims(monkeypatch):
    monkeypatch.setattr(subprocess_utils.os, "name", "nt")
    monkeypatch.setattr(
        subprocess_utils.shutil,
        "which",
        lambda command: r"C:\Program Files\nodejs\npm.CMD" if command == "npm" else None,
    )

    parts = split_command("npm run test")

    assert parts == [r"C:\Program Files\nodejs\npm.CMD", "run", "test"]


def test_numerical_witness_runs_unquoted_absolute_python_command(tmp_path):
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import json\n"
        "print(json.dumps({'score': 1.25}))\n",
        encoding="utf-8",
    )
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "command": f"{sys.executable} {probe}",
                "values": {"score": 1.25},
                "tolerance": 1e-6,
            }
        ),
        encoding="utf-8",
    )

    result = NumericalWitness(timeout=5).run(str(baseline), str(tmp_path))

    assert result.verdict == "PASS"


def test_validate_command_prefix_blocks_wrapper_command_chaining(tmp_path):
    script = tmp_path / "safe.cmd"
    script.write_text("@echo off\r\necho ok\r\n", encoding="utf-8")

    valid, detail = validate_command_prefix_with_detail(
        f'cmd /c "{script}" && del /s /q C:\\*',
        cwd=tmp_path,
    )

    assert valid is False
    assert detail is not None
    assert "unsafe shell control operator" in detail


def test_validate_command_prefix_allows_repo_local_powershell_script(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    script = scripts_dir / "verify.ps1"
    script.write_text("Write-Output 'ok'\n", encoding="utf-8")

    valid, detail = validate_command_prefix_with_detail(
        r'powershell -NoProfile -File .\scripts\verify.ps1',
        cwd=tmp_path,
    )

    assert valid is True
    assert detail is None
