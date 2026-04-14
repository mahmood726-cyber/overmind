from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from overmind.config import AppConfig, RunnerDefinition
from overmind.isolation.worktree_manager import WorktreeManager
from overmind.runners.base import BaseRunnerAdapter
from overmind.runners.claude_runner import ClaudeRunnerAdapter
from overmind.runners.codex_runner import CodexRunnerAdapter
from overmind.runners.gemini_runner import GeminiRunnerAdapter
from overmind.runners.protocols import INTERACTIVE, ONE_SHOT, PIPE
from overmind.runners.runner_registry import RunnerRegistry
from overmind.sessions.session_manager import SessionManager
from overmind.sessions.terminal_session import TerminalSession
from overmind.storage.db import StateDatabase
from overmind.storage.models import Assignment, ProjectRecord, RunnerRecord


# ---------------------------------------------------------------------------
# Protocol property tests
# ---------------------------------------------------------------------------

def test_interactive_protocol_properties():
    assert INTERACTIVE.name == "interactive"
    assert INTERACTIVE.close_stdin_after_prompt is False
    assert INTERACTIVE.supports_intervention is True
    assert INTERACTIVE.capacity_error_patterns == ()


def test_one_shot_protocol_properties():
    assert ONE_SHOT.name == "one_shot"
    assert ONE_SHOT.close_stdin_after_prompt is True
    assert ONE_SHOT.supports_intervention is False
    assert ONE_SHOT.capacity_error_patterns == ()


def test_pipe_protocol_properties():
    assert PIPE.name == "pipe"
    assert PIPE.close_stdin_after_prompt is False
    assert PIPE.supports_intervention is True
    assert len(PIPE.capacity_error_patterns) == 5


# ---------------------------------------------------------------------------
# Gemini prompt wrapper
# ---------------------------------------------------------------------------

def test_gemini_prompt_wrapper_adds_prefix():
    raw = "Explain this code."
    wrapped = PIPE.wrap_prompt(raw)
    assert wrapped.startswith("Be concise.")
    assert wrapped.endswith(raw)
    assert "no unicode borders" in wrapped


def test_interactive_prompt_wrapper_is_identity():
    raw = "Hello world"
    assert INTERACTIVE.wrap_prompt(raw) == raw


def test_one_shot_prompt_wrapper_is_identity():
    raw = "Hello world"
    assert ONE_SHOT.wrap_prompt(raw) == raw


# ---------------------------------------------------------------------------
# Gemini output filter
# ---------------------------------------------------------------------------

def test_gemini_filter_drops_star_line():
    assert PIPE.filter_output("★ Insight ─────") is None


def test_gemini_filter_drops_heavy_border():
    assert PIPE.filter_output("═══════════════════") is None


def test_gemini_filter_drops_light_border():
    assert PIPE.filter_output("─────────────────") is None


def test_gemini_filter_drops_indented_border():
    assert PIPE.filter_output("   ═══════════════") is None


def test_gemini_filter_keeps_real_content():
    line = "  result = x + y"
    assert PIPE.filter_output(line) == line


def test_gemini_filter_keeps_empty_line():
    assert PIPE.filter_output("") == ""


def test_interactive_filter_passes_all():
    assert INTERACTIVE.filter_output("★ Insight ─────") == "★ Insight ─────"


# ---------------------------------------------------------------------------
# Gemini capacity error patterns
# ---------------------------------------------------------------------------

def test_gemini_capacity_patterns_match():
    patterns = PIPE.capacity_error_patterns
    assert "too many people" in patterns
    assert "at capacity" in patterns
    assert "overloaded" in patterns
    assert "try again later" in patterns
    assert "temporarily unavailable" in patterns


def test_claude_codex_have_no_capacity_patterns():
    assert INTERACTIVE.capacity_error_patterns == ()
    assert ONE_SHOT.capacity_error_patterns == ()


# ---------------------------------------------------------------------------
# Adapter protocol wiring
# ---------------------------------------------------------------------------

def _make_definition(runner_type: str) -> RunnerDefinition:
    return RunnerDefinition(
        runner_id=f"{runner_type}_test",
        type=runner_type,
        mode="terminal",
        command=f'"{sys.executable}" -V',
        environment="windows",
    )


def test_claude_adapter_returns_interactive():
    adapter = ClaudeRunnerAdapter(_make_definition("claude"))
    assert adapter.protocol() is INTERACTIVE


def test_codex_adapter_returns_one_shot():
    adapter = CodexRunnerAdapter(_make_definition("codex"))
    assert adapter.protocol() is ONE_SHOT


def test_gemini_adapter_returns_pipe():
    adapter = GeminiRunnerAdapter(_make_definition("gemini"))
    assert adapter.protocol() is PIPE


def test_base_adapter_defaults_to_interactive():
    adapter = BaseRunnerAdapter(_make_definition("unknown"))
    assert adapter.protocol() is INTERACTIVE


def test_session_manager_resolves_bare_codex_command_and_rewrites_exec(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: r"C:\Tools\codex.CMD" if name == "codex" else None)
    manager = SessionManager(tmp_path)
    runner = RunnerRecord(
        runner_id="codex_main",
        runner_type="codex",
        environment="windows",
        command="codex",
    )

    command = manager._launch_command(runner)

    assert command.startswith('"C:\\Tools\\codex.CMD"')
    assert "--dangerously-bypass-approvals-and-sandbox" in command
    assert "exec --skip-git-repo-check -" in command


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@test.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True, capture_output=True)
    (path / "README.md").write_text("# Test\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "init"], check=True, capture_output=True)


def test_session_manager_uses_worktree_for_isolated_assignment(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)

    class DummyProcess:
        def __init__(self) -> None:
            self.finished = False

        def poll(self):
            return 0 if self.finished else None

        def terminate(self) -> None:
            self.finished = True

        def wait(self, timeout=None) -> int:
            self.finished = True
            return 0

    def fake_start(self, prompt: str) -> None:
        self.process = DummyProcess()

    monkeypatch.setattr(TerminalSession, "start", fake_start)

    manager = SessionManager(
        tmp_path / "transcripts",
        worktree_manager=WorktreeManager(tmp_path / "worktrees"),
        isolation_mode="worktree",
    )
    runner = RunnerRecord(
        runner_id="codex_main",
        runner_type="codex",
        environment="windows",
        command="codex",
    )
    project = ProjectRecord(
        project_id="proj-1",
        name="Repo",
        root_path=str(repo),
        is_git_repo=True,
    )
    assignment = Assignment(
        runner_id=runner.runner_id,
        task_id="task-1",
        project_id=project.project_id,
        prompt="do work",
        trace_id="trace-1",
        requires_isolation=True,
    )

    started = manager.dispatch(
        [assignment],
        {runner.runner_id: runner},
        {project.project_id: project},
    )

    assert started == ["task-1"]
    session = next(iter(manager.sessions.values()))
    assert session.cwd != repo
    assert (session.cwd / "README.md").exists()

    worktree_path = session.cwd
    session.process.finished = True  # type: ignore[union-attr]
    manager.collect_output()
    assert not worktree_path.exists()


def test_session_manager_strict_worktree_fails_closed_for_non_git_project(tmp_path, monkeypatch):
    def fake_start(self, prompt: str) -> None:
        raise AssertionError("start should not be called")

    monkeypatch.setattr(TerminalSession, "start", fake_start)

    manager = SessionManager(
        tmp_path / "transcripts",
        worktree_manager=WorktreeManager(tmp_path / "worktrees"),
        isolation_mode="strict_worktree",
    )
    runner = RunnerRecord(
        runner_id="codex_main",
        runner_type="codex",
        environment="windows",
        command="codex",
    )
    project = ProjectRecord(
        project_id="proj-1",
        name="Non Git",
        root_path=str(tmp_path / "plain"),
        is_git_repo=False,
    )
    Path(project.root_path).mkdir()
    assignment = Assignment(
        runner_id=runner.runner_id,
        task_id="task-1",
        project_id=project.project_id,
        prompt="do work",
        trace_id="trace-1",
        requires_isolation=True,
    )

    started = manager.dispatch(
        [assignment],
        {runner.runner_id: runner},
        {project.project_id: project},
    )

    assert started == []
    assert manager.sessions == {}


# ---------------------------------------------------------------------------
# RunnerRegistry.adapter_for
# ---------------------------------------------------------------------------

def test_adapter_for_returns_correct_adapter(tmp_path):
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir()
    data_dir.mkdir()

    (config_dir / "roots.yaml").write_text(
        "scan_roots: []\n"
        "scan_rules:\n"
        "  include_git_repos: true\n"
        "  include_non_git_apps: true\n"
        "  incremental_scan: true\n"
        "  max_depth: 2\n"
        "guidance_filenames:\n"
        "  - \"README.md\"\n",
        encoding="utf-8",
    )
    (config_dir / "runners.yaml").write_text(
        "runners:\n"
        "  - runner_id: claude_main\n"
        "    type: claude\n"
        "    mode: terminal\n"
        f"    command: '\"{sys.executable}\" -V'\n"
        "    environment: windows\n"
        "  - runner_id: codex_main\n"
        "    type: codex\n"
        "    mode: terminal\n"
        f"    command: '\"{sys.executable}\" -V'\n"
        "    environment: windows\n"
        "  - runner_id: gemini_main\n"
        "    type: gemini\n"
        "    mode: terminal\n"
        f"    command: '\"{sys.executable}\" -V'\n"
        "    environment: windows\n",
        encoding="utf-8",
    )
    (config_dir / "policies.yaml").write_text(
        "concurrency:\n  default_active_sessions: 1\n  max_active_sessions: 1\n  degraded_sessions: 1\n"
        "limits:\n  idle_timeout_min: 10\n  summary_trigger_output_lines: 400\n"
        "routing: {}\n"
        "risk_policy: {}\n",
        encoding="utf-8",
    )
    (config_dir / "projects_ignore.yaml").write_text(
        "ignored_directories: []\nignored_file_suffixes: []\n",
        encoding="utf-8",
    )
    (config_dir / "verification_profiles.yaml").write_text(
        "profiles: {}\nproject_rules: []\n",
        encoding="utf-8",
    )

    config = AppConfig.from_directory(
        config_dir=config_dir, data_dir=data_dir, db_path=data_dir / "state.db"
    )
    db = StateDatabase(config.db_path)
    try:
        registry = RunnerRegistry(config=config, db=db)

        claude_adapter = registry.adapter_for("claude_main")
        assert isinstance(claude_adapter, ClaudeRunnerAdapter)
        assert claude_adapter.protocol() is INTERACTIVE

        codex_adapter = registry.adapter_for("codex_main")
        assert isinstance(codex_adapter, CodexRunnerAdapter)
        assert codex_adapter.protocol() is ONE_SHOT

        gemini_adapter = registry.adapter_for("gemini_main")
        assert isinstance(gemini_adapter, GeminiRunnerAdapter)
        assert gemini_adapter.protocol() is PIPE

        assert registry.adapter_for("nonexistent") is None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Protocol is frozen
# ---------------------------------------------------------------------------

def test_protocol_is_frozen():
    import pytest
    with pytest.raises(AttributeError):
        INTERACTIVE.name = "changed"  # type: ignore[misc]
