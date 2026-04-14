from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Callable

from overmind.isolation.worktree_manager import WorktreeManager
from overmind.runners.protocols import INTERACTIVE, RunnerProtocol
from overmind.sessions.terminal_session import TerminalSession
from overmind.sessions.transcript_store import TranscriptStore
from overmind.storage.models import Assignment, ProjectRecord, RunnerRecord, SessionObservation

EXEC_SUBCOMMAND_PATTERN = re.compile(r"\bexec\b", re.IGNORECASE)
SKIP_GIT_REPO_CHECK_PATTERN = re.compile(
    r"(^|\s)--skip-git-repo-check(\s|$)",
    re.IGNORECASE,
)
SANDBOX_FLAG_PATTERN = re.compile(
    r"(^|\s)(-s|--sandbox)\s+\S+|--full-auto|--dangerously-bypass-approvals-and-sandbox",
    re.IGNORECASE,
)
APPROVAL_FLAG_PATTERN = re.compile(
    r"(^|\s)(-a|--ask-for-approval)\s+\S+|--full-auto|--dangerously-bypass-approvals-and-sandbox",
    re.IGNORECASE,
)


class SessionManager:
    def __init__(
        self,
        transcripts_dir: Path,
        output_blocker: Callable[[str], str | None] | None = None,
        worktree_manager: WorktreeManager | None = None,
        isolation_mode: str = "none",
    ) -> None:
        self.transcript_store = TranscriptStore(transcripts_dir)
        self.max_active_sessions = 1
        self.sessions: dict[str, TerminalSession] = {}
        self.output_blocker = output_blocker
        self.worktree_manager = worktree_manager
        self.isolation_mode = isolation_mode.strip().lower()

    def reconcile(self, max_active_sessions: int) -> None:
        self.max_active_sessions = max_active_sessions
        active_sessions = list(self.sessions.values())
        if len(active_sessions) <= max_active_sessions:
            return
        for session in active_sessions[max_active_sessions:]:
            self._dispose_session(session.session_id, stop=True)

    def dispatch(
        self,
        assignments: list[Assignment],
        runners: dict[str, RunnerRecord],
        projects: dict[str, ProjectRecord],
        protocols: dict[str, RunnerProtocol] | None = None,
    ) -> list[str]:
        started: list[str] = []
        if self.active_count() >= self.max_active_sessions:
            return started
        protocols = protocols or {}
        active_project_roots = self.active_project_roots()

        for assignment in assignments:
            if self.active_count() >= self.max_active_sessions:
                break
            if assignment.task_id in self.active_tasks():
                continue
            runner = runners.get(assignment.runner_id)
            project = projects.get(assignment.project_id)
            if not runner or not project:
                continue
            cwd, cleanup_callback = self._prepare_cwd(project, assignment, active_project_roots)
            if cwd is None:
                continue
            session_id = f"{assignment.runner_id}_{assignment.task_id}"
            session = TerminalSession(
                session_id=session_id,
                runner_id=assignment.runner_id,
                task_id=assignment.task_id,
                trace_id=assignment.trace_id or assignment.task_id,
                command=self._launch_command(runner),
                cwd=cwd,
                project_root=Path(project.root_path),
                cleanup_callback=cleanup_callback,
                transcript_store=self.transcript_store,
                protocol=protocols.get(assignment.runner_id, INTERACTIVE),
                output_blocker=self.output_blocker,
            )
            try:
                session.start(assignment.prompt)
            except Exception:
                session.cleanup()
                raise
            self.sessions[session_id] = session
            active_project_roots.add(str(Path(project.root_path)))
            started.append(assignment.task_id)
        return started

    def collect_output(self) -> list[SessionObservation]:
        observations: list[SessionObservation] = []
        finished: list[str] = []
        for session_id, session in list(self.sessions.items()):
            observation = session.observe()
            if observation.lines or observation.exit_code is not None:
                observations.append(observation)
            if observation.exit_code is not None:
                finished.append(session_id)
        for session_id in finished:
            self._dispose_session(session_id, stop=False)
        return observations

    def apply_interventions(self, actions: list[dict[str, str]]) -> None:
        for action in actions:
            task_id = action.get("task_id")
            session = self._find_by_task(task_id) if task_id else None
            if not session:
                continue
            if action.get("action") == "send_message":
                if not session.protocol.supports_intervention:
                    continue
                session.send(action.get("message", ""))
            elif action.get("action") == "pause":
                self._dispose_session(session.session_id, stop=True)

    def active_assignments(self) -> dict[str, str]:
        return {
            session.runner_id: session.task_id
            for session in self.sessions.values()
            if session.process and session.process.poll() is None
        }

    def active_tasks(self) -> set[str]:
        return {session.task_id for session in self.sessions.values()}

    def active_count(self) -> int:
        return len(self.active_assignments())

    def active_project_roots(self) -> set[str]:
        return {
            str(session.project_root)
            for session in self.sessions.values()
            if session.process and session.process.poll() is None and session.project_root is not None
        }

    def _find_by_task(self, task_id: str) -> TerminalSession | None:
        for session in self.sessions.values():
            if session.task_id == task_id:
                return session
        return None

    def _dispose_session(self, session_id: str, *, stop: bool) -> None:
        session = self.sessions.pop(session_id, None)
        if session is None:
            return
        if stop:
            session.stop()
        session.cleanup()

    def _prepare_cwd(
        self,
        project: ProjectRecord,
        assignment: Assignment,
        active_project_roots: set[str],
    ) -> tuple[Path | None, Callable[[], None] | None]:
        project_root = Path(project.root_path)
        if not self._should_use_worktree(project_root, assignment, active_project_roots):
            return project_root, None
        if self.worktree_manager is None:
            if self._worktree_required(assignment, project_root, active_project_roots):
                return None, None
            return project_root, None
        worktree_path = self.worktree_manager.create(project_root, assignment.task_id)
        if worktree_path is None:
            if self._worktree_required(assignment, project_root, active_project_roots):
                return None, None
            return project_root, None

        def cleanup() -> None:
            self.worktree_manager.cleanup(project_root, worktree_path, assignment.task_id)

        return worktree_path, cleanup

    def _should_use_worktree(
        self,
        project_root: Path,
        assignment: Assignment,
        active_project_roots: set[str],
    ) -> bool:
        if self.isolation_mode not in {"worktree", "strict_worktree", "strict"}:
            return False
        if assignment.requires_isolation:
            return True
        if self.worktree_manager is None:
            return str(project_root) in active_project_roots
        return self.worktree_manager.needs_isolation(project_root, active_project_roots)

    def _worktree_required(
        self,
        assignment: Assignment,
        project_root: Path,
        active_project_roots: set[str],
    ) -> bool:
        if self.isolation_mode in {"strict", "strict_worktree"}:
            return True
        return str(project_root) in active_project_roots

    def _launch_command(self, runner: RunnerRecord) -> str:
        command = runner.command.strip()
        if runner.runner_type.lower() != "codex":
            return self._resolve_executable(command)

        executable = self._command_executable(command)
        if self._command_stem(executable) != "codex":
            return self._resolve_executable(command)

        if EXEC_SUBCOMMAND_PATTERN.search(command):
            normalized = command
            if not SANDBOX_FLAG_PATTERN.search(normalized) and not APPROVAL_FLAG_PATTERN.search(normalized):
                normalized = EXEC_SUBCOMMAND_PATTERN.sub(
                    " --dangerously-bypass-approvals-and-sandbox exec",
                    normalized,
                    count=1,
                )
            if not SKIP_GIT_REPO_CHECK_PATTERN.search(normalized):
                normalized = EXEC_SUBCOMMAND_PATTERN.sub(
                    "exec --skip-git-repo-check",
                    normalized,
                    count=1,
                )
            return self._resolve_executable(normalized)

        prefix_parts: list[str] = []
        if not SANDBOX_FLAG_PATTERN.search(command) and not APPROVAL_FLAG_PATTERN.search(command):
            prefix_parts.append("--dangerously-bypass-approvals-and-sandbox")
        suffix_parts = ["exec"]
        if not SKIP_GIT_REPO_CHECK_PATTERN.search(command):
            suffix_parts.append("--skip-git-repo-check")
        suffix_parts.append("-")
        normalized = f"{command} {' '.join([*prefix_parts, *suffix_parts])}".strip()
        return self._resolve_executable(normalized)

    @staticmethod
    def _command_executable(command: str) -> str:
        stripped = command.strip()
        if stripped.startswith('"'):
            parts = stripped.split('"', 2)
            return parts[1] if len(parts) > 1 else stripped.strip('"')
        return stripped.split(" ", 1)[0]

    @staticmethod
    def _command_stem(executable: str) -> str:
        basename = executable.strip().strip('"').strip("'").replace("\\", "/").rsplit("/", 1)[-1]
        if "." in basename:
            basename = basename.rsplit(".", 1)[0]
        return basename.lower()

    @classmethod
    def _resolve_executable(cls, command: str) -> str:
        executable = cls._command_executable(command)
        if not executable:
            return command
        if any(token in executable for token in ("\\", "/", ":")):
            return command
        resolved = shutil.which(executable)
        if not resolved:
            return command
        suffix = command[len(executable):]
        return f'"{resolved}"{suffix}'
