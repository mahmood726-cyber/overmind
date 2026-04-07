# Overmind v2.0 — Runner Differentiation, DAG Dependencies, Dry-Run, Worktree Isolation

> Design spec for the four highest-impact features identified from agent orchestration
> research. All four directly reduce wasted tokens and prevent quality regressions.
>
> Date: 2026-04-07
> Status: APPROVED

## Context

Overmind v0.2.0 (53/53 tests, ~4,600 lines) orchestrates Claude Code, Codex CLI, and
Gemini CLI as terminal subprocesses with persistent memory and dreaming. Four gaps
remain that directly impact efficiency and quality:

1. All three runners get identical prompts and stdin handling despite different protocols
2. Tasks have no dependency ordering (build may run after test)
3. No way to preview what would be dispatched without burning agent tokens
4. Concurrent agents on the same project can corrupt each other's working directory

## Feature 1: Runner Adapter Differentiation

### Problem

The three CLI tools have fundamentally different protocols:

| | Claude Code | Codex CLI | Gemini CLI |
|---|------------|-----------|------------|
| Stdin mode | Interactive (line-by-line, stays open) | One-shot (close stdin after prompt) | Pipe (write prompt, keep open) |
| Prompt style | Conversational, supports nudges | Structured task block, single shot | Conversational |
| CLI args | `claude` (interactive) | `codex exec -` (stdin pipe) | `gemini` |
| Intervention | Send follow-up via stdin | Cannot (must restart) | Send follow-up via stdin |

Currently `TerminalSession` uses a regex (`ONE_SHOT_STDIN_PATTERN`) to detect Codex.
This is fragile and doesn't capture the full protocol difference.

### Design

New `overmind/runners/protocols.py` defines three protocol classes:

```python
class RunnerProtocol:
    name: str                    # "interactive", "one_shot", "pipe"
    close_stdin_after_prompt: bool
    supports_intervention: bool
    prompt_wrapper: Callable[[str], str]  # format raw prompt for this runner

INTERACTIVE = RunnerProtocol(
    name="interactive",
    close_stdin_after_prompt=False,
    supports_intervention=True,
    prompt_wrapper=lambda p: p,  # Claude takes raw text
)

ONE_SHOT = RunnerProtocol(
    name="one_shot",
    close_stdin_after_prompt=True,
    supports_intervention=False,
    prompt_wrapper=lambda p: p,  # Codex takes raw text via stdin
)

PIPE = RunnerProtocol(
    name="pipe",
    close_stdin_after_prompt=False,
    supports_intervention=True,
    prompt_wrapper=lambda p: p,  # Gemini takes raw text
)

# Gemini-specific known issues (handled in adapter + parser):
# 1. VERBOSE OUTPUT: Gemini wraps responses in decorative "Insight" blocks
#    (★ Insight ──────...) that waste tokens. The adapter's output_filter
#    strips these before evidence parsing.
# 2. CAPACITY ERRORS: Gemini sometimes refuses with "too many people using"
#    or similar capacity messages. Treated like rate_limit — pause runner
#    and retry later.
```

Each protocol also defines an `output_filter` and `capacity_error_patterns`:

```python
class RunnerProtocol:
    name: str
    close_stdin_after_prompt: bool
    supports_intervention: bool
    prompt_wrapper: Callable[[str], str]
    output_filter: Callable[[str], str]       # strip noise from output lines
    capacity_error_patterns: list[str]        # strings that indicate runner is unavailable
```

Gemini's output_filter strips decorative box-drawing lines (─────, ★ Insight, etc.)
before the evidence extractor sees them — reducing false positives and noise.

Gemini's capacity_error_patterns include "too many people", "capacity", "overloaded",
"try again later". These are detected by the quota tracker alongside existing
rate_limit patterns, causing the runner to enter RATE_LIMITED + cooldown.
```

Each adapter subclass returns its protocol:

```python
class ClaudeRunnerAdapter(BaseRunnerAdapter):
    def protocol(self) -> RunnerProtocol:
        return INTERACTIVE

class CodexRunnerAdapter(BaseRunnerAdapter):
    def protocol(self) -> RunnerProtocol:
        return ONE_SHOT

class GeminiRunnerAdapter(BaseRunnerAdapter):
    def protocol(self) -> RunnerProtocol:
        return PIPE
    # Gemini prompt_wrapper prepends: "Be concise. No decorative formatting,
    # no insight boxes, no unicode borders. Print commands and results only."
    # Gemini output_filter strips lines matching r"^[★─═]+|^[\s]*[─═]{4,}"
```

`TerminalSession.start()` uses the protocol instead of the `ONE_SHOT_STDIN_PATTERN` regex:

```python
def start(self, prompt: str, protocol: RunnerProtocol) -> None:
    # ... start process ...
    if prompt:
        wrapped = protocol.prompt_wrapper(prompt)
        self.send(wrapped)
        if protocol.close_stdin_after_prompt:
            self._close_stdin()
```

`SessionManager.apply_interventions()` checks `protocol.supports_intervention` before
sending messages. For Codex (one_shot), interventions are logged but not sent.

### Config

`config/runners.yaml` adds optional `protocol` field (defaults inferred from `type`):

```yaml
runners:
  - runner_id: claude_main
    type: claude
    mode: terminal
    command: "claude-code"
    environment: windows
    # protocol: interactive (inferred from type=claude)
```

`RunnerDefinition` in `config.py` gains `protocol: str = ""` field. If empty,
inferred from `type` by the adapter.

### Changes

| File | What |
|------|------|
| Create: `overmind/runners/protocols.py` | Protocol dataclass + 3 instances |
| Modify: `overmind/runners/base.py` | Add `protocol()` method returning default |
| Modify: `overmind/runners/claude_runner.py` | Return INTERACTIVE protocol |
| Modify: `overmind/runners/codex_runner.py` | Return ONE_SHOT protocol |
| Modify: `overmind/runners/gemini_runner.py` | Return PIPE protocol |
| Modify: `overmind/config.py` | Add protocol field to RunnerDefinition |
| Modify: `overmind/sessions/terminal_session.py` | Accept protocol, remove regex |
| Modify: `overmind/sessions/session_manager.py` | Pass protocol to session, check before intervention |
| Modify: `overmind/runners/runner_registry.py` | Expose adapter instances for protocol lookup |
| Create: `tests/unit/test_protocols.py` | Protocol behavior tests |

---

## Feature 2: DAG Task Dependencies

### Problem

`TaskGenerator` creates baseline verification tasks per project. When a project has
build + test + browser_test, all three checks are in one task's `required_verification`
list, so the verifier runs them sequentially. But if the user or a future generator
creates separate tasks (e.g., "build" task and "test" task), there's no way to say
"test must wait for build to complete."

### Design

`TaskRecord` gains a `blocked_by: list[str]` field — a list of task IDs that must
reach `COMPLETED` status before this task becomes eligible for scheduling.

`TaskQueue.queued()` currently returns tasks in `QUEUED` or `DISCOVERED` status. It
will additionally filter out tasks whose `blocked_by` list contains any task that is
not yet `COMPLETED` or `ARCHIVED`.

`TaskGenerator.generate()` when creating multiple tasks for the same project, chains
them: build_task has no blockers, test_task blocked_by build_task, browser_task
blocked_by test_task.

The `Scheduler` and `Prioritizer` see only unblocked queued tasks — no changes needed.

### Changes

| File | What |
|------|------|
| Modify: `overmind/storage/models.py` | Add `blocked_by: list[str]` to TaskRecord |
| Modify: `overmind/tasks/task_queue.py` | Filter blocked tasks in `queued()` |
| Modify: `overmind/tasks/task_generator.py` | Chain dependencies when generating |
| Modify: `overmind/tasks/task_models.py` | Accept blocked_by in build_baseline_task |
| Create: `tests/unit/test_task_dependencies.py` | DAG filtering and chaining tests |

---

## Feature 3: Dry-Run Mode

### Problem

Each `run_once` tick that dispatches a session burns agent tokens and time. No way to
preview what would happen without committing resources.

### Design

`Orchestrator.run_once()` gains a `dry_run: bool = False` parameter. When true:

1. Scan, generate, prioritize, schedule all run normally
2. Assignments are computed (including full prompts)
3. **Dispatch is skipped** — no sessions started, no tasks transitioned to RUNNING
4. Returns the same payload but with `"dry_run": True` and `"would_dispatch"` instead
   of `"assignments"`
5. Task state is **not modified** (tasks stay QUEUED)

The CLI adds `--dry-run` flag to `run-once`.

For `run-loop`, `--dry-run` runs a single iteration in dry-run mode and exits
(running a loop in dry-run mode repeatedly would be pointless).

### Changes

| File | What |
|------|------|
| Modify: `overmind/core/orchestrator.py` | Add dry_run flag to run_once, skip dispatch |
| Modify: `overmind/cli.py` | Add --dry-run to run-once and run-loop |
| Create: `tests/unit/test_dry_run.py` | Verify no sessions started, no state change |

---

## Feature 4: Git Worktree Isolation

### Problem

When two runners are assigned to the same project, both operate in the same directory.
File writes, git operations, and test runs can interfere.

### Design

New module `overmind/isolation/worktree_manager.py`:

```python
class WorktreeManager:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir  # e.g., data/worktrees

    def create(self, project_root: Path, task_id: str) -> Path | None:
        """Create a git worktree for this task. Returns worktree path or None if not a git repo."""

    def cleanup(self, worktree_path: Path) -> None:
        """Remove worktree and its branch."""

    def needs_isolation(self, project_root: Path, active_sessions: dict[str, str]) -> bool:
        """True if another session is already working on this project."""
```

**Lifecycle:**
1. `SessionManager.dispatch()` checks if another session is active on the same project
2. If yes AND project is a git repo, call `worktree_manager.create()` to get an
   isolated working directory
3. Session uses the worktree path as its cwd instead of project root
4. When session completes (in `collect_output()`), call `worktree_manager.cleanup()`
5. Changes in the worktree are on a branch named `overmind/<task_id>`. The user
   decides whether to merge.

**Worktree creation:**
```
git -C <project_root> worktree add <base_dir>/<task_id> -b overmind/<task_id>
```

**Worktree cleanup:**
```
git -C <project_root> worktree remove <worktree_path> --force
git -C <project_root> branch -D overmind/<task_id>
```

**Policy:** `config/policies.yaml` gains:
```yaml
isolation:
  mode: worktree   # "worktree" or "none"
  base_dir: ""     # empty = data_dir / "worktrees"
```

When `mode: none`, no isolation is performed (current behavior).

### Changes

| File | What |
|------|------|
| Create: `overmind/isolation/__init__.py` | Package init |
| Create: `overmind/isolation/worktree_manager.py` | Create/cleanup/needs_isolation |
| Modify: `overmind/config.py` | Add isolation config |
| Modify: `overmind/sessions/session_manager.py` | Worktree check before dispatch, cleanup after |
| Modify: `config/policies.yaml` | Add isolation section |
| Create: `tests/unit/test_worktree_manager.py` | Worktree lifecycle tests |

---

## Testing Strategy

Target: 53 existing + ~20 new = ~73 tests.

| Test area | What |
|-----------|------|
| Protocols | Each adapter returns correct protocol, session uses it |
| DAG dependencies | Blocked tasks filtered, chains generated correctly |
| Dry-run | No sessions started, no state transitions, full preview returned |
| Worktrees | Create, cleanup, needs_isolation logic, non-git project skipped |
| Integration | run_once with dry_run, run_once with protocol-aware dispatch |

---

## Success Criteria

1. All 53 existing tests pass (no regressions)
2. ~20 new tests pass
3. Claude/Codex/Gemini get protocol-appropriate stdin handling
4. Tasks with unfinished blockers don't get dispatched
5. `--dry-run` shows what would happen without starting sessions
6. Concurrent same-project assignments use worktrees when configured
7. `ONE_SHOT_STDIN_PATTERN` regex removed from terminal_session.py
