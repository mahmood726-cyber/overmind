"""The scheduled .bat launchers must find a real interpreter or fail loudly.

The nightly stopped on 2026-05-17 with no alert: both launchers defaulted to a
literal per-user path that does not exist under another Windows account.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
RESOLVER = REPO / "scripts" / "resolve_python.bat"
LAUNCHERS = ["nightly_verify.bat", "consolidate_memory.bat"]

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="cmd.exe semantics")


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k.upper() != "OVERMIND_PYTHON"}
    env["LOCALAPPDATA"] = str(tmp_path / "no-such-appdata")
    env["PATH"] = str(tmp_path / "empty-path") + os.pathsep + str(Path(env["SYSTEMROOT"]) / "System32")
    env.update(extra)
    return env


def _resolve(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    script = f'@call "{RESOLVER}"\r\n@echo RC=%errorlevel% PY=%OVERMIND_PYTHON%\r\n'
    probe = Path(env["LOCALAPPDATA"]).parent / "probe.bat"
    probe.write_text(script, encoding="ascii")
    return subprocess.run(["cmd", "/c", str(probe)], env=env, capture_output=True, text=True, timeout=30)


@pytest.mark.parametrize("name", LAUNCHERS)
def test_launcher_names_no_literal_user_profile(name):
    text = (REPO / "scripts" / name).read_text(encoding="utf-8")
    code = [line for line in text.splitlines() if not line.upper().lstrip().startswith("REM")]
    assert not re.search(r"[A-Za-z]:\\Users\\[A-Za-z]", "\n".join(code))


@pytest.mark.parametrize("name", LAUNCHERS)
def test_launcher_stops_when_resolver_fails(name):
    text = (REPO / "scripts" / name).read_text(encoding="utf-8")
    assert 'call "%~dp0resolve_python.bat"' in text
    after = text.split("resolve_python.bat", 1)[1]
    assert re.search(r"if errorlevel 1 exit /b", after)


@windows_only
def test_no_interpreter_fails_closed(tmp_path):
    result = _resolve(_env(tmp_path))
    assert "RC=9" in result.stdout
    assert "no usable Python" in result.stderr


@windows_only
def test_missing_override_fails_closed(tmp_path):
    result = _resolve(_env(tmp_path, OVERMIND_PYTHON=str(tmp_path / "ghost.exe")))
    assert "RC=9" in result.stdout


@windows_only
def test_override_that_exists_is_honoured(tmp_path):
    fake = tmp_path / "custom python.exe"
    fake.write_bytes(b"")
    result = _resolve(_env(tmp_path, OVERMIND_PYTHON=str(fake)))
    assert "RC=0" in result.stdout
    assert f"PY={fake}" in result.stdout


@windows_only
def test_per_user_install_is_found_without_path(tmp_path):
    appdata = tmp_path / "appdata"
    target = appdata / "Programs" / "Python" / "Python313" / "python.exe"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"")
    result = _resolve(_env(tmp_path, LOCALAPPDATA=str(appdata)))
    assert "RC=0" in result.stdout
    assert f"PY={target}" in result.stdout


@windows_only
def test_python_on_path_is_the_fallback(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    target = bin_dir / "python.exe"
    target.write_bytes(b"")
    env = _env(tmp_path)
    env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]
    result = _resolve(env)
    assert "RC=0" in result.stdout
    assert f"PY={target}" in result.stdout
