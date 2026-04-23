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


def test_split_command_raises_on_malformed_quoting():
    command = '"C:\\Program Files\\Python\\python.exe" -c "print(1)'

    try:
        split_command(command)
    except ValueError as exc:
        assert "command could not be parsed" in str(exc)
    else:
        raise AssertionError("Expected split_command to fail closed on malformed quoting")


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


def test_validate_command_prefix_blocks_unparseable_command():
    valid, detail = validate_command_prefix_with_detail(
        '"C:\\Program Files\\Python\\python.exe" -c "print(1)',
        cwd="C:\\overmind",
    )

    assert valid is False
    assert detail is not None
    assert "could not be parsed" in detail


def test_safe_subprocess_env_strips_inheritance_vectors(monkeypatch):
    """LD_PRELOAD, PYTHONSTARTUP, GIT_*, npm_config_* must not leak into the
    verifier subprocess environment."""
    from overmind.subprocess_utils import safe_subprocess_env

    monkeypatch.setenv("LD_PRELOAD", "/tmp/evil.so")
    monkeypatch.setenv("PYTHONSTARTUP", "/tmp/evil.py")
    monkeypatch.setenv("GIT_DIR", "/tmp/evil-git")
    monkeypatch.setenv("npm_config_registry", "https://evil.example/")
    monkeypatch.setenv("PATH", "/usr/bin")

    scrubbed = safe_subprocess_env()

    assert "LD_PRELOAD" not in scrubbed
    assert "PYTHONSTARTUP" not in scrubbed
    assert "GIT_DIR" not in scrubbed
    assert "npm_config_registry" not in scrubbed
    assert "PATH" in scrubbed


def test_verifier_popen_kwargs_sets_utf8_and_env(tmp_path, monkeypatch):
    """Single source of truth for verification subprocess launch."""
    from overmind.subprocess_utils import verifier_popen_kwargs

    monkeypatch.setenv("LD_PRELOAD", "/tmp/evil.so")

    kwargs = verifier_popen_kwargs(str(tmp_path))

    assert kwargs["cwd"] == str(tmp_path)
    assert kwargs["shell"] is False
    assert kwargs["encoding"] == "utf-8"
    assert kwargs["errors"] == "replace"
    assert "LD_PRELOAD" not in kwargs["env"]


def test_verifier_popen_kwargs_sets_new_process_group_on_windows():
    import subprocess as _subprocess
    import sys as _sys

    from overmind.subprocess_utils import verifier_popen_kwargs

    kwargs = verifier_popen_kwargs("/tmp")
    if _sys.platform == "win32":
        assert kwargs.get("creationflags", 0) & _subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        assert "creationflags" not in kwargs


def test_kill_process_tree_uses_taskkill_on_windows(monkeypatch):
    """P0-1 parity: orchestrator and verifier both rely on taskkill /T to reach
    pytest-xdist workers and any other spawned subprocesses."""
    import subprocess as _subprocess
    import sys as _sys

    if _sys.platform != "win32":
        import pytest
        pytest.skip("Windows-specific taskkill behavior")

    from overmind.subprocess_utils import kill_process_tree

    captured: dict[str, object] = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        return _subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(_subprocess, "run", fake_run)

    class StubProc:
        pid = 9999

        def kill(self):
            captured.setdefault("fallback_kill_called", True)

    kill_process_tree(StubProc())

    assert captured["args"][0] == "taskkill"
    assert "/T" in captured["args"]
    assert "/F" in captured["args"]
    assert str(9999) in captured["args"]
