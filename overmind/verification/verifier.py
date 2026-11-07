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


_QUIET_SYNTAX_CHECK_RE = re.compile(r"^node\s+(?:-c|--check)\s+[\w./\-]+$", re.IGNORECASE)


def _is_quiet_syntax_check(command: str) -> bool:
    """True only for a bare `node -c <file>` / `node --check <file>`.

    No chaining, redirection or extra arguments: anything else that is silent
    on success stays UNVERIFIED.
    """
    return bool(_QUIET_SYNTAX_CHECK_RE.match(command.strip()))


class VerificationEngine:
    def __init__(self, artifacts_dir: Path, verification_timeout: int = 900) -> None:
        self.artifacts_dir = artifacts_dir
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.planner = VerificationPlanner()
        self.policy_guard = PolicyGuard()
        self.verification_timeout = verification_timeout

    @staticmethod
    def _read_git_head(root_path: str) -> str | None:
        """Read the exact checkout identity without running project commands.

        Fail closed on missing Git, inaccessible worktrees, invalid revisions,
        or a timed-out metadata lookup. No shell or network operation is used.
        """
        # A saturated machine can exceed a short timeout on a healthy repo, so
        # allow 30s and retry a *timeout* once. Any other failure (not a repo,
        # bad revision, OSError) is deterministic: no retry, fail closed.
        completed = None
        for _attempt in range(2):
            try:
                completed = subprocess.run(
                    ["git", "--no-optional-locks", "rev-parse", "--verify", "HEAD"],
                    cwd=root_path,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=safe_subprocess_env(),
                    timeout=30,
                    check=False,
                )
                break
            except subprocess.TimeoutExpired:
                continue
            except (OSError, ValueError):
                return None
        if completed is None:
            return None
        head = completed.stdout.strip().lower()
        if completed.returncode != 0 or not re.fullmatch(
            r"(?:[0-9a-f]{40}|[0-9a-f]{64})", head
        ):
            return None
        return head

    def _artifact_log_path(self, trace_id: str, task_id: str, check: str, index: int) -> Path:
        """Keep command evidence within artifacts_dir on Windows and POSIX.

        Preserve legacy simple names for compatibility. Unsafe or excessively
        long identities use a bounded ASCII name with a digest over the full
        original tuple so distinct normalized names do not alias.
        """
        raw = f"{trace_id}_{task_id}_{check}_{index}.log"
        # The legacy underscore-joined name is ambiguous if a trace or task
        # contains underscores: ("a_b", "c") and ("a", "b_c") alias. Windows
        # also treats case-only names as identical. Reserve legacy filenames
        # for tuples whose trace/task boundaries are unambiguous and whose
        # filename is case-stable; use the identity digest otherwise.
        if (
            len(raw.encode("utf-8")) <= 180
            and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", raw)
            and "_" not in str(trace_id)
            and "_" not in str(task_id)
            and raw == raw.lower()
        ):
            return self.artifacts_dir / raw

        parts = [str(trace_id), str(task_id), str(check), index]
        digest = hashlib.sha256(
            json.dumps(parts, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:24]

        def slug(value: object) -> str:
            return re.sub(r"[^A-Za-z0-9_-]", "_", str(value))[:24] or "id"

        name = f"verify_{slug(trace_id)}_{slug(task_id)}_{slug(check)}_{index}_{digest}.log"
        return self.artifacts_dir / name

    def _write_artifact_log(self, base_path: Path, payload: str) -> Path:
        """Create per-execution evidence without replacing existing run logs.

        Exclusive creation avoids a check-then-write race across simultaneous
        verifications and refuses to follow a pre-existing log-path symlink.
        Keep the first run's legacy basename; later runs receive a suffix.
        Exhaustion is an evidence failure, not permission to overwrite.
        """
        for attempt in range(1000):
            candidate = (
                base_path if attempt == 0 else
                base_path.with_name(f"{base_path.stem}.{attempt}{base_path.suffix}")
            )
            try:
                with candidate.open("x", encoding="utf-8") as handle:
                    handle.write(payload)
                return candidate
            except FileExistsError:
                continue
        raise OSError("verification log namespace exhausted")

    def run(
        self,
        task: TaskRecord,
        project: ProjectRecord,
        *,
        expected_commit_sha: str | None = None,
    ) -> VerificationResult:
        completed_checks: list[str] = []
        skipped_checks: list[str] = []
        details: list[str] = []
        success = True
        cached_results: dict[str, tuple[bool, str]] = {}
        trace_id = task.trace_id or task.task_id
        commands_executed = 0
        # Freeze the contract before the planner or any runner may mutate it.
        required_checks = list(task.required_verification)

        # Git-marked projects must not treat passing commands as proof for an
        # unknown or moving revision. An explicit expected SHA also fences
        # callers that do not set ProjectRecord.is_git_repo.
        git_bound = project.is_git_repo or expected_commit_sha is not None
        expected = None
        if expected_commit_sha is not None:
            if not isinstance(expected_commit_sha, str) or not re.fullmatch(
                r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", expected_commit_sha
            ):
                return VerificationResult(
                    task_id=task.task_id, trace_id=trace_id, success=False,
                    required_checks=required_checks, completed_checks=[],
                    skipped_checks=[],
                    details=["verification: unverified; invalid expected Git commit SHA"],
                )
            expected = expected_commit_sha.lower()

        initial_head = None
        if git_bound:
            initial_head = self._read_git_head(project.root_path)
            if initial_head is None:
                return VerificationResult(
                    task_id=task.task_id, trace_id=trace_id, success=False,
                    required_checks=required_checks, completed_checks=[],
                    skipped_checks=[],
                    details=["verification: unverified; Git HEAD unavailable before planning"],
                )
            if expected is not None and initial_head != expected:
                return VerificationResult(
                    task_id=task.task_id, trace_id=trace_id, success=False,
                    required_checks=required_checks, completed_checks=[],
                    skipped_checks=[],
                    details=[
                        f"verification: unverified; Git HEAD {initial_head} "
                        f"does not match expected {expected}"
                    ],
                )
            details.append(f"verification: Git HEAD start={initial_head}")

        # Freeze the command plan immediately after planning. A shared mutable
        # planner dict/list must not authorize commands appended during a runner
        # callback, or certify a command plan different from the one executed.
        planner_output = self.planner.plan(task, project)
        try:
            planned_checks = {
                check: tuple(commands) for check, commands in planner_output.items()
            }
        except (AttributeError, TypeError, ValueError):
            return VerificationResult(
                task_id=task.task_id, trace_id=trace_id, success=False,
                required_checks=required_checks, completed_checks=[],
                skipped_checks=[],
                details=["verification: unverified; malformed verification command plan"],
            )
        # A planning step may itself change the checkout. Refuse to launch
        # verification commands under a stale planning snapshot.
        if git_bound:
            planned_head = self._read_git_head(project.root_path)
            if planned_head is None or planned_head != initial_head:
                reason = (
                    "Git HEAD unavailable after planning" if planned_head is None
                    else f"Git HEAD changed during planning; start={initial_head} end={planned_head}"
                )
                return VerificationResult(
                    task_id=task.task_id, trace_id=trace_id, success=False,
                    required_checks=required_checks, completed_checks=[],
                    skipped_checks=[], details=[*details, f"verification: unverified; {reason}"],
                )
        if task.required_verification != required_checks:
            return VerificationResult(
                task_id=task.task_id,
                trace_id=trace_id,
                success=False,
                required_checks=required_checks,
                completed_checks=[],
                skipped_checks=[],
                details=["verification: unverified; verification contract changed during planning"],
            )
        # The returned command plan must cover the task's declared proof
        # obligations. A missing check is not an authorized skip, even if
        # commands from other checks execute and produce positive output.
        if not required_checks:
            success = False
            details.append("verification: unverified; no required verification checks declared")
        for required_check in required_checks:
            if required_check not in planned_checks:
                success = False
                details.append(
                    f"{required_check}: unverified; required verification check omitted from plan"
                )

        # A planner may not broaden the task's proof contract. Unexpected
        # commands are not authorized verification evidence; refuse them before
        # execution and make the resulting completion fail closed.
        for check in planned_checks:
            if check not in required_checks:
                success = False
                details.append(
                    f"{check}: unverified; planner supplied undeclared verification check"
                )

        for check, commands in planned_checks.items():
            if check not in required_checks:
                continue
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
                    artifact_path = self._write_artifact_log(
                        self._artifact_log_path(trace_id, task.task_id, check, index),
                        f"$ {command}\n\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}",
                    )
                except (OSError, ValueError) as exc:
                    details.append(
                        f"{check}: unverified; command log unavailable ({type(exc).__name__})"
                    )
                    cached_results[command] = (False, check)
                    check_passed = False
                    success = False
                    break
                details.append(f"{check}: exit={exit_code} command={command} log={artifact_path.name}")
                if exit_code == -1:
                    if "timed out" in stderr.lower():
                        details.append(f"{check}: timed out after {self.verification_timeout}s")
                    elif stderr:
                        details.append(f"{check}: {stderr}")
                # An exit code of zero with no observable output is not
                # sufficient completion evidence. A genuinely quiet command
                # may still have succeeded, but its status remains unverified
                # rather than becoming a false PASS.
                # Exception: `node -c <file>` / `node --check <file>` are
                # silent on success by design (exit 0 is the whole signal).
                empty_output = (
                    exit_code == 0
                    and not (stdout.strip() or stderr.strip())
                    and not _is_quiet_syntax_check(command)
                )
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

        # Recompare the original planner-owned structure after execution.
        # This fences late changes even when the planned check names remain
        # unchanged, while the frozen tuple plan prevents newly appended
        # commands from being executed in this verification.
        try:
            plan_changed = {
                check: tuple(commands) for check, commands in planner_output.items()
            } != planned_checks
        except (AttributeError, TypeError, ValueError):
            plan_changed = True
        if plan_changed:
            success = False
            details.append("verification: unverified; verification command plan changed during execution")

        # Do not accept a successful run if its proof obligations changed
        # while commands were executing.
        if task.required_verification != required_checks:
            success = False
            details.append("verification: unverified; verification contract changed during execution")

        if git_bound:
            final_head = self._read_git_head(project.root_path)
            if final_head is None:
                success = False
                details.append("verification: unverified; Git HEAD unavailable after execution")
            elif final_head != initial_head:
                success = False
                details.append(
                    f"verification: unverified; Git HEAD changed during execution; "
                    f"start={initial_head} end={final_head}"
                )
            else:
                details.append(f"verification: Git HEAD verified commit={final_head}")

        return VerificationResult(
            task_id=task.task_id,
            trace_id=trace_id,
            success=success,
            required_checks=required_checks,
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
