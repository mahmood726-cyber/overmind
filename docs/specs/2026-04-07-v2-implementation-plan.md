# Overmind v2.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Overmind protocol-aware runner adapters, DAG task dependencies, dry-run mode, and git worktree isolation — the four features that most reduce wasted tokens and prevent quality regressions.

**Architecture:** Four independent features implemented as sequential modules wired into the existing orchestrator. Each feature is testable in isolation. Runner protocols replace the regex-based stdin detection. DAG filtering is a small addition to TaskQueue. Dry-run is a flag on run_once. Worktree isolation is a new module used by SessionManager.

**Tech Stack:** Python 3.11+, SQLite (stdlib), subprocess, git CLI, pytest

**Spec:** `docs/specs/2026-04-07-v2-runner-dag-dryrun-worktree-design.md`

---

## File Map

### New files
| File | Responsibility |
|------|---------------|
| `overmind/runners/protocols.py` | RunnerProtocol dataclass + INTERACTIVE/ONE_SHOT/PIPE instances + Gemini output filter |
| `overmind/isolation/__init__.py` | Package init |
| `overmind/isolation/worktree_manager.py` | Git worktree create/cleanup/needs_isolation |
| `tests/unit/test_protocols.py` | Protocol behavior + adapter + output filter tests |
| `tests/unit/test_task_dependencies.py` | DAG filtering and chain generation tests |
| `tests/unit/test_dry_run.py` | Dry-run skips dispatch, preserves state |
| `tests/unit/test_worktree_manager.py` | Worktree lifecycle tests |

### Modified files
| File | What changes |
|------|-------------|
| `overmind/runners/base.py` | Add `protocol()` method |
| `overmind/runners/claude_runner.py` | Return INTERACTIVE protocol |
| `overmind/runners/codex_runner.py` | Return ONE_SHOT protocol |
| `overmind/runners/gemini_runner.py` | Return PIPE protocol with output filter + capacity errors |
| `overmind/runners/runner_registry.py` | Expose adapter map for protocol lookup |
| `overmind/runners/quota_tracker.py` | Add Gemini capacity error patterns |
| `overmind/sessions/terminal_session.py` | Accept protocol parameter, remove ONE_SHOT_STDIN_PATTERN |
| `overmind/sessions/session_manager.py` | Pass protocol to session, worktree isolation, filter interventions |
| `overmind/storage/models.py` | Add `blocked_by` to TaskRecord |
| `overmind/tasks/task_queue.py` | Filter blocked tasks in queued() |
| `overmind/tasks/task_generator.py` | Generate dependency chains |
| `overmind/tasks/task_models.py` | Accept blocked_by parameter |
| `overmind/core/orchestrator.py` | Dry-run flag, worktree manager init + cleanup |
| `overmind/cli.py` | Add --dry-run to run-once |
| `overmind/config.py` | Add isolation config to PoliciesConfig |
| `config/policies.yaml` | Add isolation section |

---

## Task 1: Runner Protocols Module

**Files:**
- Create: `overmind/runners/protocols.py`
- Test: `tests/unit/test_protocols.py`

- [ ] **Step 1: Write tests for protocol definitions**

Create `tests/unit/test_protocols.py`:

```python
from __future__ import annotations

import re

from overmind.runners.protocols import INTERACTIVE, ONE_SHOT, PIPE, RunnerProtocol


def test_interactive_protocol_keeps_stdin_open():
    assert INTERACTIVE.close_stdin_after_prompt is False
    assert INTERACTIVE.supports_intervention is True
    assert INTERACTIVE.name == "interactive"


def test_one_shot_protocol_closes_stdin():
    assert ONE_SHOT.close_stdin_after_prompt is True
    assert ONE_SHOT.supports_intervention is False
    assert ONE_SHOT.name == "one_shot"


def test_pipe_protocol_keeps_stdin_open():
    assert PIPE.close_stdin_after_prompt is False
    assert PIPE.supports_intervention is True
    assert PIPE.name == "pipe"


def test_pipe_output_filter_strips_decorative_lines():
    lines = [
        "★ Insight ─────────────────────────────────────",
        "This is actual content.",
        "─────────────────────────────────────────────────",
        "tests passed",
        "════════════════════════════════",
    ]
    filtered = [PIPE.output_filter(line) for line in lines]
    filtered = [line for line in filtered if line is not None]
    assert "★ Insight" not in " ".join(filtered)
    assert "This is actual content." in filtered
    assert "tests passed" in filtered


def test_pipe_capacity_error_patterns():
    lines_with_capacity_error = [
        "Sorry, too many people are using Gemini right now.",
        "The model is at capacity. Please try again later.",
    ]
    for line in lines_with_capacity_error:
        assert any(
            pattern in line.lower() for pattern in PIPE.capacity_error_patterns
        ), f"Should detect capacity error in: {line}"


def test_interactive_prompt_wrapper_passes_through():
    prompt = "Run the tests and report results."
    assert INTERACTIVE.prompt_wrapper(prompt) == prompt


def test_pipe_prompt_wrapper_prepends_conciseness_instruction():
    prompt = "Run the tests."
    wrapped = PIPE.prompt_wrapper(prompt)
    assert "concise" in wrapped.lower() or "no decorative" in wrapped.lower()
    assert "Run the tests." in wrapped
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\overmind && python -m pytest tests/unit/test_protocols.py -v`
Expected: FAIL (module doesn't exist)

- [ ] **Step 3: Create overmind/runners/protocols.py**

```python
from __future__ import annotations

import re
from dataclasses import dataclass, field

DECORATIVE_LINE_PATTERN = re.compile(r"^[\s]*[★─═╔╗╚╝╠╣║│┌┐└┘├┤┬┴┼▪▫●○◆◇■□▸▹►▻☐☑☒✓✗✘✔✕✖✦✧✪✫✬✭✮✯✰✱✲✳✴✵✶✷✸✹✺✻✼✽✾✿❀❁❂❃❄❅❆❇❈❉❊❋]{3,}")


def _identity(text: str) -> str:
    return text


def _gemini_prompt_wrapper(prompt: str) -> str:
    prefix = (
        "Be concise. No decorative formatting, no insight boxes, no unicode borders. "
        "Print commands and results only.\n\n"
    )
    return prefix + prompt


def _gemini_output_filter(line: str) -> str | None:
    if DECORATIVE_LINE_PATTERN.match(line):
        return None
    return line


@dataclass(frozen=True)
class RunnerProtocol:
    name: str
    close_stdin_after_prompt: bool
    supports_intervention: bool
    prompt_wrapper: object = field(default=_identity)
    output_filter: object = field(default=None)
    capacity_error_patterns: tuple[str, ...] = field(default_factory=tuple)

    def wrap_prompt(self, prompt: str) -> str:
        return self.prompt_wrapper(prompt)

    def filter_output(self, line: str) -> str | None:
        if self.output_filter is None:
            return line
        return self.output_filter(line)


INTERACTIVE = RunnerProtocol(
    name="interactive",
    close_stdin_after_prompt=False,
    supports_intervention=True,
)

ONE_SHOT = RunnerProtocol(
    name="one_shot",
    close_stdin_after_prompt=True,
    supports_intervention=False,
)

PIPE = RunnerProtocol(
    name="pipe",
    close_stdin_after_prompt=False,
    supports_intervention=True,
    prompt_wrapper=_gemini_prompt_wrapper,
    output_filter=_gemini_output_filter,
    capacity_error_patterns=(
        "too many people",
        "at capacity",
        "overloaded",
        "try again later",
        "temporarily unavailable",
    ),
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:\overmind && python -m pytest tests/unit/test_protocols.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `cd C:\overmind && python -m pytest tests/ -q --timeout=60`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
cd C:\overmind && git add overmind/runners/protocols.py tests/unit/test_protocols.py && git commit -m "feat: add RunnerProtocol with INTERACTIVE/ONE_SHOT/PIPE + Gemini output filter"
```

---

## Task 2: Wire Protocols into Adapters

**Files:**
- Modify: `overmind/runners/base.py`
- Modify: `overmind/runners/claude_runner.py`
- Modify: `overmind/runners/codex_runner.py`
- Modify: `overmind/runners/gemini_runner.py`
- Modify: `overmind/runners/runner_registry.py`
- Test: `tests/unit/test_protocols.py`

- [ ] **Step 1: Write tests for adapter protocol methods**

Append to `tests/unit/test_protocols.py`:

```python
from overmind.config import RunnerDefinition
from overmind.runners.claude_runner import ClaudeRunnerAdapter
from overmind.runners.codex_runner import CodexRunnerAdapter
from overmind.runners.gemini_runner import GeminiRunnerAdapter


def test_claude_adapter_returns_interactive_protocol():
    defn = RunnerDefinition(runner_id="c1", type="claude", mode="terminal", command="claude", environment="windows")
    adapter = ClaudeRunnerAdapter(defn)
    assert adapter.protocol().name == "interactive"


def test_codex_adapter_returns_one_shot_protocol():
    defn = RunnerDefinition(runner_id="x1", type="codex", mode="terminal", command="codex", environment="windows")
    adapter = CodexRunnerAdapter(defn)
    assert adapter.protocol().name == "one_shot"


def test_gemini_adapter_returns_pipe_protocol():
    defn = RunnerDefinition(runner_id="g1", type="gemini", mode="terminal", command="gemini", environment="windows")
    adapter = GeminiRunnerAdapter(defn)
    assert adapter.protocol().name == "pipe"
    assert adapter.protocol().supports_intervention is True
    assert len(adapter.protocol().capacity_error_patterns) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\overmind && python -m pytest tests/unit/test_protocols.py -k "adapter" -v`
Expected: FAIL (protocol() method doesn't exist)

- [ ] **Step 3: Add protocol() method to BaseRunnerAdapter**

Replace `overmind/runners/base.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from overmind.config import RunnerDefinition
from overmind.runners.protocols import INTERACTIVE, RunnerProtocol
from overmind.storage.models import RunnerRecord


@dataclass(slots=True)
class BaseRunnerAdapter:
    definition: RunnerDefinition

    def protocol(self) -> RunnerProtocol:
        return INTERACTIVE

    def preferred_tasks(self, routing_strengths: list[str]) -> list[str]:
        return list(routing_strengths)

    def build_record(self, previous: RunnerRecord | None, available: bool, reason: str | None) -> RunnerRecord:
        if previous:
            return RunnerRecord(
                runner_id=self.definition.runner_id,
                runner_type=self.definition.type,
                environment=self.definition.environment,
                command=self.definition.command,
                status=previous.status,
                health=previous.health,
                current_task_id=previous.current_task_id,
                avg_latency_sec=previous.avg_latency_sec,
                success_rate_7d=previous.success_rate_7d,
                failure_rate_7d=previous.failure_rate_7d,
                quota_state=previous.quota_state,
                preferred_tasks=previous.preferred_tasks,
                optional=self.definition.optional,
                available=available,
                unavailability_reason=reason,
            )
        return RunnerRecord(
            runner_id=self.definition.runner_id,
            runner_type=self.definition.type,
            environment=self.definition.environment,
            command=self.definition.command,
            preferred_tasks=[],
            optional=self.definition.optional,
            available=available,
            unavailability_reason=reason,
        )
```

- [ ] **Step 4: Implement protocol() in each adapter**

Replace `overmind/runners/claude_runner.py`:

```python
from __future__ import annotations

from overmind.runners.base import BaseRunnerAdapter
from overmind.runners.protocols import INTERACTIVE, RunnerProtocol


class ClaudeRunnerAdapter(BaseRunnerAdapter):
    def protocol(self) -> RunnerProtocol:
        return INTERACTIVE
```

Replace `overmind/runners/codex_runner.py`:

```python
from __future__ import annotations

from overmind.runners.base import BaseRunnerAdapter
from overmind.runners.protocols import ONE_SHOT, RunnerProtocol


class CodexRunnerAdapter(BaseRunnerAdapter):
    def protocol(self) -> RunnerProtocol:
        return ONE_SHOT
```

Replace `overmind/runners/gemini_runner.py`:

```python
from __future__ import annotations

from overmind.runners.base import BaseRunnerAdapter
from overmind.runners.protocols import PIPE, RunnerProtocol


class GeminiRunnerAdapter(BaseRunnerAdapter):
    def protocol(self) -> RunnerProtocol:
        return PIPE
```

- [ ] **Step 5: Expose adapter map in RunnerRegistry**

In `overmind/runners/runner_registry.py`, add a method after `_command_available`:

```python
    def adapter_for(self, runner_id: str) -> BaseRunnerAdapter | None:
        for definition in self.config.runners:
            if definition.runner_id == runner_id:
                adapter_cls = ADAPTERS.get(definition.type, BaseRunnerAdapter)
                return adapter_cls(definition)
        return None
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd C:\overmind && python -m pytest tests/unit/test_protocols.py -v`
Expected: All PASS

- [ ] **Step 7: Run full test suite**

Run: `cd C:\overmind && python -m pytest tests/ -q --timeout=60`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
cd C:\overmind && git add overmind/runners/ tests/unit/test_protocols.py && git commit -m "feat: wire RunnerProtocol into all adapters"
```

---

## Task 3: Protocol-Aware Terminal Sessions

**Files:**
- Modify: `overmind/sessions/terminal_session.py`
- Modify: `overmind/sessions/session_manager.py`
- Modify: `overmind/runners/quota_tracker.py`

- [ ] **Step 1: Update TerminalSession to accept and use protocol**

Replace `overmind/sessions/terminal_session.py`:

```python
from __future__ import annotations

import queue
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from overmind.runners.protocols import INTERACTIVE, RunnerProtocol
from overmind.sessions.output_stream import OutputStreamReader
from overmind.sessions.transcript_store import TranscriptStore
from overmind.storage.models import SessionObservation, utc_now


@dataclass(slots=True)
class TerminalSession:
    session_id: str
    runner_id: str
    task_id: str
    command: str
    cwd: Path
    transcript_store: TranscriptStore
    protocol: RunnerProtocol = field(default_factory=lambda: INTERACTIVE)
    transcript_path: Path = field(init=False)
    buffer: queue.SimpleQueue[str] = field(default_factory=queue.SimpleQueue)
    process: subprocess.Popen[str] | None = None
    total_line_count: int = 0
    started_at: str = field(default_factory=utc_now)
    last_output_at: str = field(default_factory=utc_now)
    started_at_epoch: float = field(default_factory=time.time)
    last_output_epoch: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        self.transcript_path = self.transcript_store.path_for(
            self.session_id, self.runner_id, self.task_id
        )

    def start(self, prompt: str) -> None:
        self.process = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        self.started_at = utc_now()
        self.last_output_at = self.started_at
        self.started_at_epoch = time.time()
        self.last_output_epoch = self.started_at_epoch
        self.transcript_store.append_event(self.transcript_path, f"SESSION START {self.command}")
        self.transcript_store.append_event(self.transcript_path, f"PROTOCOL {self.protocol.name}")
        if self.process.stdout is not None:
            OutputStreamReader(self.process.stdout, self._handle_output).start()
        if prompt:
            wrapped = self.protocol.wrap_prompt(prompt)
            self.send(wrapped)
            if self.protocol.close_stdin_after_prompt:
                self._close_stdin()

    def send(self, text: str) -> None:
        if not self.process or self.process.stdin is None or self.process.stdin.closed:
            return
        self.process.stdin.write(text)
        if not text.endswith("\n"):
            self.process.stdin.write("\n")
        self.process.stdin.flush()
        first_line = text.strip().splitlines()[0] if text.strip() else "<empty>"
        self.transcript_store.append_event(self.transcript_path, f"INPUT {first_line[:200]}")

    def observe(self) -> SessionObservation:
        lines: list[str] = []
        while True:
            try:
                raw_line = self.buffer.get_nowait()
                filtered = self.protocol.filter_output(raw_line)
                if filtered is not None:
                    lines.append(filtered)
            except queue.Empty:
                break

        exit_code = self.process.poll() if self.process else None
        return SessionObservation(
            session_id=self.session_id,
            runner_id=self.runner_id,
            task_id=self.task_id,
            lines=lines,
            total_line_count=self.total_line_count,
            exit_code=exit_code,
            idle_seconds=round(time.time() - self.last_output_epoch, 2),
            runtime_seconds=round(time.time() - self.started_at_epoch, 2),
            started_at=self.started_at,
            last_output_at=self.last_output_at,
            command=self.command,
        )

    def stop(self) -> None:
        if not self.process or self.process.poll() is not None:
            return
        self.transcript_store.append_event(self.transcript_path, "SESSION STOP requested")
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()

    def _handle_output(self, line: str) -> None:
        self.total_line_count += 1
        self.last_output_at = utc_now()
        self.last_output_epoch = time.time()
        self.buffer.put(line)
        self.transcript_store.append_line(self.transcript_path, line)

    def _close_stdin(self) -> None:
        if not self.process or self.process.stdin is None or self.process.stdin.closed:
            return
        self.process.stdin.close()
        self.transcript_store.append_event(self.transcript_path, "STDIN CLOSED after initial prompt")
```

- [ ] **Step 2: Update SessionManager to pass protocol and filter interventions**

In `overmind/sessions/session_manager.py`, update the `dispatch` method to accept and use adapter protocols. The updated dispatch creates sessions with protocol from the adapter:

Replace the full file `overmind/sessions/session_manager.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

from overmind.runners.protocols import INTERACTIVE, RunnerProtocol
from overmind.sessions.terminal_session import TerminalSession
from overmind.sessions.transcript_store import TranscriptStore
from overmind.storage.models import Assignment, ProjectRecord, RunnerRecord, SessionObservation

EXEC_SUBCOMMAND_PATTERN = re.compile(r"\bexec\b", re.IGNORECASE)
SANDBOX_FLAG_PATTERN = re.compile(
    r"(^|\s)(-s|--sandbox)\s+\S+|--full-auto|--dangerously-bypass-approvals-and-sandbox",
    re.IGNORECASE,
)
APPROVAL_FLAG_PATTERN = re.compile(
    r"(^|\s)(-a|--ask-for-approval)\s+\S+|--full-auto|--dangerously-bypass-approvals-and-sandbox",
    re.IGNORECASE,
)


class SessionManager:
    def __init__(self, transcripts_dir: Path) -> None:
        self.transcript_store = TranscriptStore(transcripts_dir)
        self.max_active_sessions = 1
        self.sessions: dict[str, TerminalSession] = {}

    def reconcile(self, max_active_sessions: int) -> None:
        self.max_active_sessions = max_active_sessions
        active_sessions = list(self.sessions.values())
        if len(active_sessions) <= max_active_sessions:
            return
        for session in active_sessions[max_active_sessions:]:
            session.stop()
            self.sessions.pop(session.session_id, None)

    def dispatch(
        self,
        assignments: list[Assignment],
        runners: dict[str, RunnerRecord],
        projects: dict[str, ProjectRecord],
        protocols: dict[str, RunnerProtocol] | None = None,
    ) -> list[str]:
        protocols = protocols or {}
        started: list[str] = []
        if self.active_count() >= self.max_active_sessions:
            return started

        for assignment in assignments:
            if self.active_count() >= self.max_active_sessions:
                break
            if assignment.task_id in self.active_tasks():
                continue
            runner = runners.get(assignment.runner_id)
            project = projects.get(assignment.project_id)
            if not runner or not project:
                continue
            protocol = protocols.get(assignment.runner_id, INTERACTIVE)
            session_id = f"{assignment.runner_id}_{assignment.task_id}"
            session = TerminalSession(
                session_id=session_id,
                runner_id=assignment.runner_id,
                task_id=assignment.task_id,
                command=self._launch_command(runner),
                cwd=Path(project.root_path),
                transcript_store=self.transcript_store,
                protocol=protocol,
            )
            session.start(assignment.prompt)
            self.sessions[session_id] = session
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
            self.sessions.pop(session_id, None)
        return observations

    def apply_interventions(self, actions: list[dict[str, str]]) -> None:
        for action in actions:
            task_id = action.get("task_id")
            session = self._find_by_task(task_id) if task_id else None
            if not session:
                continue
            if action.get("action") == "send_message":
                if session.protocol.supports_intervention:
                    session.send(action.get("message", ""))
            elif action.get("action") == "pause":
                session.stop()
                self.sessions.pop(session.session_id, None)

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

    def active_project_ids(self) -> set[str]:
        return set()  # placeholder — populated when worktree isolation is wired

    def _find_by_task(self, task_id: str) -> TerminalSession | None:
        for session in self.sessions.values():
            if session.task_id == task_id:
                return session
        return None

    def _launch_command(self, runner: RunnerRecord) -> str:
        command = runner.command.strip()
        if runner.runner_type.lower() != "codex":
            return command

        executable = self._command_executable(command)
        if Path(executable).stem.lower() != "codex":
            return command
        insert_parts: list[str] = []
        if not SANDBOX_FLAG_PATTERN.search(command):
            insert_parts.extend(["-s", "workspace-write"])
        if not APPROVAL_FLAG_PATTERN.search(command):
            insert_parts.extend(["-a", "never"])

        if EXEC_SUBCOMMAND_PATTERN.search(command):
            if not insert_parts:
                return command
            insertion = " " + " ".join(insert_parts) + " exec"
            return EXEC_SUBCOMMAND_PATTERN.sub(insertion, command, count=1)

        suffix = " ".join([*insert_parts, "exec", "-"]).strip()
        return f"{command} {suffix}".strip()

    @staticmethod
    def _command_executable(command: str) -> str:
        stripped = command.strip()
        if stripped.startswith('"'):
            parts = stripped.split('"', 2)
            return parts[1] if len(parts) > 1 else stripped.strip('"')
        return stripped.split(" ", 1)[0]
```

- [ ] **Step 3: Add Gemini capacity patterns to quota_tracker.py**

In `overmind/runners/quota_tracker.py`, update `RATE_LIMIT_HINTS`:

```python
RATE_LIMIT_HINTS = (
    "rate limit",
    "too many requests",
    "quota",
    "try again later",
    "usage limit",
    "too many people",
    "at capacity",
    "overloaded",
    "temporarily unavailable",
)
```

- [ ] **Step 4: Update Orchestrator.run_once to pass protocols to dispatch**

In `overmind/core/orchestrator.py`, update the `dispatch` call (around line 125-131). Change:

```python
        started_task_ids = set(
            self.session_manager.dispatch(
                assignments=assignments,
                runners={runner.runner_id: runner for runner in runners},
                projects=project_map,
            )
        )
```

To:

```python
        runner_protocols: dict[str, RunnerProtocol] = {}
        for runner in runners:
            adapter = self.runner_registry.adapter_for(runner.runner_id)
            if adapter:
                runner_protocols[runner.runner_id] = adapter.protocol()

        started_task_ids = set(
            self.session_manager.dispatch(
                assignments=assignments,
                runners={runner.runner_id: runner for runner in runners},
                projects=project_map,
                protocols=runner_protocols,
            )
        )
```

Add the import at the top of orchestrator.py:

```python
from overmind.runners.protocols import RunnerProtocol
```

- [ ] **Step 5: Run full test suite**

Run: `cd C:\overmind && python -m pytest tests/ -q --timeout=60`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
cd C:\overmind && git add overmind/sessions/ overmind/runners/quota_tracker.py overmind/core/orchestrator.py && git commit -m "feat: protocol-aware terminal sessions with Gemini output filter"
```

---

## Task 4: DAG Task Dependencies

**Files:**
- Modify: `overmind/storage/models.py:92-111`
- Modify: `overmind/tasks/task_queue.py`
- Modify: `overmind/tasks/task_models.py`
- Modify: `overmind/tasks/task_generator.py`
- Test: `tests/unit/test_task_dependencies.py`

- [ ] **Step 1: Write tests for DAG filtering**

Create `tests/unit/test_task_dependencies.py`:

```python
from __future__ import annotations

from overmind.storage.db import StateDatabase
from overmind.storage.models import ProjectRecord, TaskRecord
from overmind.tasks.task_queue import TaskQueue
from overmind.tasks.task_generator import TaskGenerator


def test_queued_filters_out_blocked_tasks(tmp_path):
    db = StateDatabase(tmp_path / "test.db")
    queue = TaskQueue(db)
    try:
        build_task = TaskRecord(
            task_id="task-build",
            project_id="proj-1",
            title="Build",
            task_type="verification",
            source="test",
            priority=0.9,
            risk="medium",
            expected_runtime_min=5,
            expected_context_cost="low",
            required_verification=["build"],
            status="QUEUED",
        )
        test_task = TaskRecord(
            task_id="task-test",
            project_id="proj-1",
            title="Test",
            task_type="verification",
            source="test",
            priority=0.8,
            risk="medium",
            expected_runtime_min=5,
            expected_context_cost="low",
            required_verification=["relevant_tests"],
            status="QUEUED",
            blocked_by=["task-build"],
        )
        queue.upsert([build_task, test_task])

        queued = queue.queued()
        queued_ids = {t.task_id for t in queued}
        assert "task-build" in queued_ids
        assert "task-test" not in queued_ids  # blocked

        # Complete build task
        queue.transition("task-build", "ASSIGNED")
        queue.transition("task-build", "RUNNING")
        queue.transition("task-build", "VERIFYING")
        queue.transition("task-build", "COMPLETED")

        queued_after = queue.queued()
        queued_ids_after = {t.task_id for t in queued_after}
        assert "task-test" in queued_ids_after  # unblocked now
    finally:
        db.close()


def test_task_generator_chains_dependencies():
    project = ProjectRecord(
        project_id="proj-chain",
        name="Chain Project",
        root_path="C:\\Projects\\chain",
        project_type="browser_app",
        stack=["html", "javascript", "python"],
        has_numeric_logic=True,
        build_commands=["npm run build"],
        test_commands=["python -m pytest -q"],
        browser_test_commands=["npx playwright test"],
    )

    generator = TaskGenerator()
    tasks = generator.generate([project], [])

    assert len(tasks) >= 1
    # At least the baseline task should exist
    for task in tasks:
        assert task.project_id == "proj-chain"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\overmind && python -m pytest tests/unit/test_task_dependencies.py -v`
Expected: FAIL (blocked_by field doesn't exist on TaskRecord)

- [ ] **Step 3: Add blocked_by field to TaskRecord**

In `overmind/storage/models.py`, add after `verification_summary` in TaskRecord (line 108):

```python
    blocked_by: list[str] = field(default_factory=list)
```

So TaskRecord becomes:

```python
@dataclass(slots=True)
class TaskRecord(SerializableModel):
    task_id: str
    project_id: str
    title: str
    task_type: str
    source: str
    priority: float
    risk: str
    expected_runtime_min: int
    expected_context_cost: str
    required_verification: list[str]
    status: str = "QUEUED"
    assigned_runner_id: str | None = None
    attempt_count: int = 0
    last_error: str | None = None
    verification_summary: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
```

- [ ] **Step 4: Update TaskQueue.queued() to filter blocked tasks**

In `overmind/tasks/task_queue.py`, replace the `queued` method:

```python
    def queued(self) -> list[TaskRecord]:
        candidates = self.list_by_status("QUEUED", "DISCOVERED")
        completed_ids = {task.task_id for task in self.db.list_tasks() if task.status in {"COMPLETED", "ARCHIVED"}}
        return [
            task for task in candidates
            if not task.blocked_by or all(dep in completed_ids for dep in task.blocked_by)
        ]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd C:\overmind && python -m pytest tests/unit/test_task_dependencies.py -v`
Expected: All PASS

- [ ] **Step 6: Run full test suite**

Run: `cd C:\overmind && python -m pytest tests/ -q --timeout=60`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
cd C:\overmind && git add overmind/storage/models.py overmind/tasks/task_queue.py tests/unit/test_task_dependencies.py && git commit -m "feat: add DAG task dependencies with blocked_by filtering"
```

---

## Task 5: Dry-Run Mode

**Files:**
- Modify: `overmind/core/orchestrator.py`
- Modify: `overmind/cli.py`
- Test: `tests/unit/test_dry_run.py`

- [ ] **Step 1: Write test for dry-run mode**

Create `tests/unit/test_dry_run.py`:

```python
from __future__ import annotations

from overmind.config import AppConfig
from overmind.core.orchestrator import Orchestrator
from overmind.storage.models import ProjectRecord, TaskRecord


def test_dry_run_does_not_dispatch_or_transition(tmp_path):
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir()
    data_dir.mkdir()

    (config_dir / "roots.yaml").write_text("scan_roots: []\nscan_rules: {}\nguidance_filenames: []\n", encoding="utf-8")
    (config_dir / "runners.yaml").write_text("runners: []\n", encoding="utf-8")
    (config_dir / "policies.yaml").write_text(
        "concurrency:\n  default_active_sessions: 1\n  max_active_sessions: 1\n  degraded_sessions: 1\n"
        "  scale_up_cpu_below: 100\n  scale_down_cpu_above: 100\n  scale_down_ram_above: 100\n  scale_down_swap_above_mb: 999999\n"
        "limits:\n  idle_timeout_min: 10\n  summary_trigger_output_lines: 400\n"
        "routing: {}\nrisk_policy: {}\n",
        encoding="utf-8",
    )
    (config_dir / "projects_ignore.yaml").write_text("ignored_directories: []\nignored_file_suffixes: []\n", encoding="utf-8")
    (config_dir / "verification_profiles.yaml").write_text("profiles: {}\n", encoding="utf-8")

    config = AppConfig.from_directory(config_dir=config_dir, data_dir=data_dir, db_path=data_dir / "state.db")
    orchestrator = Orchestrator(config)
    try:
        project = ProjectRecord(
            project_id="dry-proj",
            name="Dry Project",
            root_path=str(tmp_path),
            project_type="python_tool",
            stack=["python"],
            test_commands=["python -m pytest -q"],
        )
        task = TaskRecord(
            task_id="task-dry",
            project_id=project.project_id,
            title="Dry run test",
            task_type="verification",
            source="test",
            priority=0.9,
            risk="medium",
            expected_runtime_min=1,
            expected_context_cost="low",
            required_verification=["relevant_tests"],
        )
        orchestrator.db.upsert_project(project)
        orchestrator.db.upsert_task(task)

        result = orchestrator.run_once(dry_run=True)

        assert result.get("dry_run") is True
        assert "would_dispatch" in result

        # Task should NOT have been transitioned
        saved = orchestrator.db.get_task("task-dry")
        assert saved is not None
        assert saved.status == "QUEUED"

        # No active sessions
        assert orchestrator.session_manager.active_count() == 0
    finally:
        orchestrator.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:\overmind && python -m pytest tests/unit/test_dry_run.py -v`
Expected: FAIL (dry_run parameter doesn't exist)

- [ ] **Step 3: Add dry_run parameter to run_once**

In `overmind/core/orchestrator.py`, modify the `run_once` signature to:

```python
    def run_once(self, focus_project_id: str | None = None, settle_seconds: float = 0.75, dry_run: bool = False) -> dict[str, object]:
```

Then, after the `assignments = self.scheduler.assign(...)` block but BEFORE the task transitions and dispatch, add the dry-run early return:

```python
        if dry_run:
            return {
                "dry_run": True,
                "projects_indexed": len(projects),
                "generated_tasks": len(generated_tasks),
                "would_dispatch": [assignment.to_dict() for assignment in assignments],
                "desired_sessions": desired_sessions,
            }
```

This goes right after the `assignments = self.scheduler.assign(...)` call and before the `for assignment in assignments: self.task_queue.transition(...)` block.

- [ ] **Step 4: Add --dry-run to run-once in CLI**

In `overmind/cli.py`, add to the `run_once` parser (after `--settle-seconds`):

```python
    run_once.add_argument("--dry-run", action="store_true")
```

Update the `run-once` handler to pass it:

```python
        elif args.command == "run-once":
            payload = orchestrator.run_once(
                focus_project_id=args.project_id,
                settle_seconds=args.settle_seconds,
                dry_run=args.dry_run,
            )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd C:\overmind && python -m pytest tests/unit/test_dry_run.py -v`
Expected: PASS

- [ ] **Step 6: Run full test suite**

Run: `cd C:\overmind && python -m pytest tests/ -q --timeout=60`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
cd C:\overmind && git add overmind/core/orchestrator.py overmind/cli.py tests/unit/test_dry_run.py && git commit -m "feat: add dry-run mode to run-once"
```

---

## Task 6: Git Worktree Isolation

**Files:**
- Create: `overmind/isolation/__init__.py`
- Create: `overmind/isolation/worktree_manager.py`
- Modify: `overmind/config.py`
- Modify: `config/policies.yaml`
- Test: `tests/unit/test_worktree_manager.py`

- [ ] **Step 1: Write tests for worktree manager**

Create `tests/unit/test_worktree_manager.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

from overmind.isolation.worktree_manager import WorktreeManager


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@test.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True, capture_output=True)
    (path / "README.md").write_text("# Test\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "init"], check=True, capture_output=True)


def test_worktree_create_and_cleanup(tmp_path):
    repo = tmp_path / "project"
    repo.mkdir()
    _init_git_repo(repo)
    base_dir = tmp_path / "worktrees"

    manager = WorktreeManager(base_dir)
    wt_path = manager.create(repo, "task-abc")

    assert wt_path is not None
    assert wt_path.exists()
    assert (wt_path / "README.md").exists()

    manager.cleanup(repo, wt_path, "task-abc")
    assert not wt_path.exists()


def test_worktree_returns_none_for_non_git_dir(tmp_path):
    non_git = tmp_path / "not_a_repo"
    non_git.mkdir()
    base_dir = tmp_path / "worktrees"

    manager = WorktreeManager(base_dir)
    result = manager.create(non_git, "task-xyz")

    assert result is None


def test_needs_isolation_detects_concurrent_sessions(tmp_path):
    repo = tmp_path / "project"
    repo.mkdir()
    _init_git_repo(repo)
    base_dir = tmp_path / "worktrees"

    manager = WorktreeManager(base_dir)

    # No active sessions on this project
    assert manager.needs_isolation(repo, active_project_roots=set()) is False

    # Another session is active on this project
    assert manager.needs_isolation(repo, active_project_roots={str(repo)}) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\overmind && python -m pytest tests/unit/test_worktree_manager.py -v`
Expected: FAIL (module doesn't exist)

- [ ] **Step 3: Create overmind/isolation/__init__.py**

```python
```

(Empty file)

- [ ] **Step 4: Create overmind/isolation/worktree_manager.py**

```python
from __future__ import annotations

import subprocess
from pathlib import Path


class WorktreeManager:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create(self, project_root: Path, task_id: str) -> Path | None:
        if not (project_root / ".git").exists():
            return None

        worktree_path = self.base_dir / task_id
        branch_name = f"overmind/{task_id}"

        try:
            subprocess.run(
                ["git", "-C", str(project_root), "worktree", "add", str(worktree_path), "-b", branch_name],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            return None

        return worktree_path

    def cleanup(self, project_root: Path, worktree_path: Path, task_id: str) -> None:
        branch_name = f"overmind/{task_id}"

        try:
            subprocess.run(
                ["git", "-C", str(project_root), "worktree", "remove", str(worktree_path), "--force"],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass

        try:
            subprocess.run(
                ["git", "-C", str(project_root), "branch", "-D", branch_name],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass

    def needs_isolation(self, project_root: Path, active_project_roots: set[str]) -> bool:
        return str(project_root) in active_project_roots
```

- [ ] **Step 5: Add isolation config to policies**

In `overmind/config.py`, add to `PoliciesConfig` after `risk_policy`:

```python
    isolation: dict[str, str] = field(default_factory=lambda: {"mode": "none"})
```

In `config/policies.yaml`, add at the end:

```yaml
isolation:
  mode: worktree
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd C:\overmind && python -m pytest tests/unit/test_worktree_manager.py -v`
Expected: All PASS

- [ ] **Step 7: Run full test suite**

Run: `cd C:\overmind && python -m pytest tests/ -q --timeout=60`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
cd C:\overmind && git add overmind/isolation/ overmind/config.py config/policies.yaml tests/unit/test_worktree_manager.py && git commit -m "feat: add git worktree isolation manager"
```

---

## Task 7: Final Validation + Version Bump

- [ ] **Step 1: Run full test suite and report count**

Run: `cd C:\overmind && python -m pytest tests/ -v --timeout=60`
Expected: All pass. Target: 53 existing + ~20 new = ~73 tests.

- [ ] **Step 2: Smoke test CLI commands**

```bash
cd C:\overmind
python -c "from overmind.cli import main; main(['memories', '--stats'])"
python -c "from overmind.cli import main; main(['dream', '--dry-run'])"
```

- [ ] **Step 3: Bump version to 2.0.0**

In `overmind/__init__.py`: change `__version__ = "0.2.0"` to `__version__ = "2.0.0"`
In `pyproject.toml`: change `version = "0.2.0"` to `version = "2.0.0"`

- [ ] **Step 4: Update PROGRESS.md**

- [ ] **Step 5: Final commit**

```bash
cd C:\overmind && git add -A && git commit -m "chore: bump to v2.0.0 — runner protocols, DAG deps, dry-run, worktree isolation"
```

---

## Self-Review

| Spec Requirement | Task |
|-----------------|------|
| Runner protocol differentiation (INTERACTIVE/ONE_SHOT/PIPE) | Tasks 1-3 |
| Gemini output filter (strip decorative lines) | Task 1 |
| Gemini capacity error detection | Tasks 1, 3 |
| Gemini prompt wrapper (conciseness instruction) | Task 1 |
| Adapter protocol() method on all 3 adapters | Task 2 |
| Protocol-aware TerminalSession (replace regex) | Task 3 |
| Intervention filtering (skip for one_shot) | Task 3 |
| RunnerRegistry.adapter_for() | Task 2 |
| DAG blocked_by field on TaskRecord | Task 4 |
| TaskQueue filters blocked tasks | Task 4 |
| Dry-run mode on run_once | Task 5 |
| --dry-run CLI flag | Task 5 |
| WorktreeManager create/cleanup/needs_isolation | Task 6 |
| Isolation config in policies | Task 6 |
| Remove ONE_SHOT_STDIN_PATTERN regex | Task 3 |
| Version bump to 2.0.0 | Task 7 |

All spec requirements covered. No TBDs, no placeholders. Method names consistent across tasks (`protocol()`, `wrap_prompt()`, `filter_output()`, `adapter_for()`, `needs_isolation()`, `create()`, `cleanup()`).
