from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from overmind.subprocess_utils import (
    kill_process_tree,
    safe_subprocess_env,
    split_command,
    validate_command_prefix_with_detail,
    verifier_popen_kwargs,
)

from overmind.storage.models import ProjectRecord, TaskRecord, VerificationResult
from overmind.verification.policy_guard import PolicyGuard
from overmind.verification.profiles import VerificationPlanner


# Backward-compatible aliases for tests that still import the private symbols.
_safe_env = safe_subprocess_env
_kill_process_tree = kill_process_tree


class VerificationEngine:
    def __init__(self, artifacts_dir: Path, verification_timeout: int = 900) -> None:
        self.artifacts_dir = artifacts_dir
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.planner = VerificationPlanner()
        self.policy_guard = PolicyGuard()
        self.verification_timeout = verification_timeout

    def _artifact_log_path(self, trace_id: str, task_id: str, check: str, index: int) -> Path:
        """Keep command evidence within artifacts_dir on Windows and POSIX.

        Preserve legacy simple names for compatibility. Unsafe or excessively
        long identities use a bounded ASCII name with a digest over the full
        original tuple so distinct normalized names do not alias.
        """
        raw = f"{trace_id}_{task_id}_{check}_{index}.log"
        if len(raw.encode("utf-8")) <= 180 and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", raw):
            return self.artifacts_dir / raw

        parts = [str(trace_id), str(task_id), str(check), index]
        digest = hashlib.sha256(
            json.dumps(parts, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:24]

        def slug(value: object) -> str:
            return re.sub(r"[^A-Za-z0-9_-]", "_", str(value))[:24] or "id"

        name = f"verify_{slug(trace_id)}_{slug(task_id)}_{slug(check)}_{index}_{digest}.log"
        return self.artifacts_dir / name

    def run(self, task: TaskRecord, project: ProjectRecord) -> VerificationResult:
        completed_checks: list[str] = []
        skipped_checks: list[str] = []
        details: list[str] = []
        success = True
        cached_results: dict[str, tuple[bool, str]] = {}
        trace_id = task.trace_id or task.task_id
        commands_executed = 0

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
                commands_executed += 1

                # A successful subprocess without a readable command log is
                # missing verification evidence, not a completed check. Unsafe
                # trace/task/check identifiers must not escape artifacts_dir.
                try:
                    artifact_path = self._artifact_log_path(trace_id, task.task_id, check, index)
                    artifact_path.write_text(
                        f"$ {command}\n\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}",
                        encoding="utf-8",
                    )
                except (OSError, ValueError) as exc:
                    details.append(
                        f"{check}: unverified; command log unavailable ({type(exc).__name__})"
                    )
                    cached_results[command] = (False, check)
                    check_passed = False
                    success = False
                    break
                details.append(f"{check}: exit={exit_code} command={command}")
                if exit_code == -1:
                    if "timed out" in stderr.lower():
                        details.append(f"{check}: timed out after {self.verification_timeout}s")
                    elif stderr:
                        details.append(f"{check}: {stderr}")
                # An exit code of zero with no observable output is not
                # sufficient completion evidence. A genuinely quiet command
                # may still have succeeded, but its status remains unverified
                # rather than becoming a false PASS.
                empty_output = exit_code == 0 and not (stdout.strip() or stderr.strip())
                if empty_output:
                    details.append(
                        f"{check}: unverified; command exited 0 with empty stdout/stderr"
                    )
                cached_results[command] = (exit_code == 0 and not empty_output, check)
                if exit_code != 0 or empty_output:
                    check_passed = False
                    success = False
                    break
            if check_passed:
                completed_checks.append(check)

        # An empty plan (or optional-only checks with no commands) must not
        # turn a lack of verification evidence into successful completion.
        if commands_executed == 0:
            success = False
            details.append("verification: no verification command executed; result unverified")

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
        try:
            proc = subprocess.Popen(split_command(command), **verifier_popen_kwargs(cwd))
            try:
                stdout, stderr = proc.communicate(timeout=self.verification_timeout)
                return proc.returncode, stdout, stderr
            except subprocess.TimeoutExpired:
                kill_process_tree(proc)
                try:
                    stdout, stderr = proc.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    stdout, stderr = "", ""
                return -1, stdout, f"Command timed out after {self.verification_timeout}s"
        except (OSError, ValueError) as exc:
            return -1, "", f"Failed to start command: {exc}"
