from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from overmind.subprocess_utils import split_command, validate_command_prefix_with_detail

from overmind.storage.models import ProjectRecord, TaskRecord, VerificationResult
from overmind.verification.policy_guard import PolicyGuard
from overmind.verification.profiles import VerificationPlanner


# Env vars the verification subprocess inherits from the parent. Anything outside
# this list (LD_PRELOAD, PYTHONSTARTUP, GIT_*, npm_config_*, etc.) is stripped so
# a malicious project directory cannot influence the verifier via environment.
_VERIFIER_ENV_ALLOWLIST = {
    "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE",
    "TEMP", "TMP", "LOCALAPPDATA", "APPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)",
    "PROGRAMDATA", "COMSPEC", "HOMEDRIVE", "HOMEPATH", "USERPROFILE", "USERNAME",
    "COMPUTERNAME", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
    "LANG", "LC_ALL", "LC_CTYPE",
    "PYTHONIOENCODING", "PYTHONUTF8",
    "VIRTUAL_ENV",
}


def _safe_env() -> dict[str, str]:
    """Return a scrubbed environment for verification subprocesses."""
    return {k: v for k, v in os.environ.items() if k.upper() in _VERIFIER_ENV_ALLOWLIST}


def _kill_process_tree(proc: subprocess.Popen) -> None:
    """Kill a subprocess plus any children it spawned (pytest-xdist workers, etc.)."""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                timeout=5,
            )
        else:
            proc.kill()
    except (OSError, subprocess.TimeoutExpired):
        try:
            proc.kill()
        except OSError:
            pass


class VerificationEngine:
    def __init__(self, artifacts_dir: Path, verification_timeout: int = 900) -> None:
        self.artifacts_dir = artifacts_dir
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.planner = VerificationPlanner()
        self.policy_guard = PolicyGuard()
        self.verification_timeout = verification_timeout

    def run(self, task: TaskRecord, project: ProjectRecord) -> VerificationResult:
        completed_checks: list[str] = []
        skipped_checks: list[str] = []
        details: list[str] = []
        success = True
        cached_results: dict[str, tuple[bool, str]] = {}
        trace_id = task.trace_id or task.task_id

        for check, commands in self.planner.plan(task, project).items():
            if not commands:
                skipped_checks.append(f"{check}: no command discovered")
                if check != "build_or_direct_evidence":
                    success = False
                continue

            check_passed = True
            for index, command in enumerate(commands, start=1):
                if command in cached_results:
                    cached_success, source_check = cached_results[command]
                    details.append(f"{check}: reused verification evidence from {source_check} command={command}")
                    if not cached_success:
                        check_passed = False
                        success = False
                        break
                    continue

                exit_code, stdout, stderr = self._run_command(command, project.root_path)

                artifact_path = self.artifacts_dir / f"{trace_id}_{task.task_id}_{check}_{index}.log"
                artifact_path.write_text(
                    f"$ {command}\n\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}",
                    encoding="utf-8",
                )
                details.append(f"{check}: exit={exit_code} command={command}")
                if exit_code == -1:
                    if "timed out" in stderr.lower():
                        details.append(f"{check}: timed out after {self.verification_timeout}s")
                    elif stderr:
                        details.append(f"{check}: {stderr}")
                cached_results[command] = (exit_code == 0, check)
                if exit_code != 0:
                    check_passed = False
                    success = False
                    break
            if check_passed:
                completed_checks.append(check)

        return VerificationResult(
            task_id=task.task_id,
            trace_id=trace_id,
            success=success,
            required_checks=task.required_verification,
            completed_checks=completed_checks,
            skipped_checks=skipped_checks,
            details=details,
        )

    def _run_command(self, command: str, cwd: str) -> tuple[int, str, str]:
        valid, detail = validate_command_prefix_with_detail(command, cwd=cwd)
        if not valid:
            return -1, "", detail or f"Blocked: command prefix not allowlisted: {command[:200]}"
        blocking_violation = next(
            (violation for violation in self.policy_guard.evaluate([command]) if violation.severity == "block"),
            None,
        )
        if blocking_violation is not None:
            return -1, "", (
                f"Blocked: policy violation {blocking_violation.rule_name}: "
                f"{blocking_violation.message}"
            )
        popen_kwargs: dict[str, object] = {
            "cwd": cwd,
            "shell": False,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "env": _safe_env(),
        }
        if sys.platform == "win32":
            # New process group so taskkill /T can reach pytest-xdist workers and
            # any other child processes spawned during verification.
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            proc = subprocess.Popen(split_command(command), **popen_kwargs)
            try:
                stdout, stderr = proc.communicate(timeout=self.verification_timeout)
                return proc.returncode, stdout, stderr
            except subprocess.TimeoutExpired:
                _kill_process_tree(proc)
                try:
                    stdout, stderr = proc.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    stdout, stderr = "", ""
                return -1, stdout, f"Command timed out after {self.verification_timeout}s"
        except OSError as exc:
            return -1, "", f"Failed to start command: {exc}"
