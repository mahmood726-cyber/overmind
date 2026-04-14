from __future__ import annotations

from pathlib import Path

from overmind.runners.protocols import ONE_SHOT
from overmind.sessions.terminal_session import TerminalSession
from overmind.sessions.transcript_store import TranscriptStore


def test_terminal_session_suppresses_prompt_echo_in_observation(tmp_path):
    session = TerminalSession(
        session_id="sess-1",
        runner_id="codex_main",
        task_id="task-1",
        command="codex exec -",
        cwd=tmp_path,
        transcript_store=TranscriptStore(tmp_path / "transcripts"),
        protocol=ONE_SHOT,
    )
    session.transcript_path = Path(tmp_path / "transcripts" / "session.log")

    session._prime_prompt_echo_budget("PROJECT:\nHello\n")
    session._handle_output("user\n")
    session._handle_output("PROJECT:\n")
    session._handle_output("Hello\n")
    session._handle_output("tests passed\n")

    observation = session.observe()

    assert observation.lines == ["tests passed\n"]


def test_terminal_session_stops_immediately_on_output_blocker(tmp_path):
    class DummyProcess:
        def __init__(self) -> None:
            self.terminated = False

        def poll(self):
            return None

        def terminate(self) -> None:
            self.terminated = True

        def wait(self, timeout=None) -> None:
            return None

    session = TerminalSession(
        session_id="sess-2",
        runner_id="codex_main",
        task_id="task-2",
        command="codex exec -",
        cwd=tmp_path,
        transcript_store=TranscriptStore(tmp_path / "transcripts"),
        protocol=ONE_SHOT,
        output_blocker=lambda line: "blocked destructive command" if "rm -rf /" in line else None,
    )
    session.transcript_path = Path(tmp_path / "transcripts" / "session-2.log")
    session.process = DummyProcess()

    session._handle_output("$ rm -rf /\n")

    observation = session.observe()

    assert session.process.terminated is True
    assert observation.lines == ["$ rm -rf /\n"]
