# Overmind v2.1.0 Progress

## v2.1.0 Completed (2026-04-07, session 3)

### Feature 1: Self-Improving Audit Loop
- AuditLoop tracks per-project verification history
- Stores audit_snapshot memories with pass rate tags
- Detects improving/degrading/stable trends
- Creates regression alerts on degradation (>5% drop)
- CLI: `overmind audit-history --project-id X`

### Feature 2: VeriMAP — Verify Functions in DAG
- `verify_command: str | None` field on TaskRecord
- Auto-assigned from project.test_commands[0] in task generators
- Orchestrator runs verify_command after agent completion, before marking COMPLETED
- Failures auto-transition to FAILED with context

### Feature 3: Q-Learning Router
- `routing_scores` table with Laplace-smoothed Q-values
- QRouter.score/record/scores_table
- Scheduler incorporates Q-values (weight 0.5) alongside hardcoded bonuses
- Orchestrator records outcomes in Q-router after each verification

### Feature 4: Output-Hash Loop Detection
- Fingerprint-based detection via MD5 of normalized content
- Normalizes: strips timestamps, dates, replaces digits with #
- Sliding window of last 20 lines, threshold 3+ repeats
- Existing exact-match detection preserved as fast path

### Feature 5: Tests-First Task Template
- `build_test_first_tasks(project)` creates 2 chained tasks
- Task 1: "Write acceptance tests" (test_writing type)
- Task 2: "Implement to pass tests" (implementation type, blocked_by task 1)
- Auto-used for projects with has_advanced_math + test_commands

### Test Results: 104/104 pass

## v0.2.0 Completed (2026-04-07, session 1)

### Bug Fixes (7/7)
- P0-1: Package data for prompts/*.txt
- P0-2: Removed C:\ from scan_roots
- P0-3: Consistent 6-element tuples in _command_priority
- P1-1: Handle subprocess.TimeoutExpired in verifier (Popen + kill)
- P1-2: SQL table name whitelist in db.py
- P1-3: Guard _last_active_timestamp against empty candidates + OSError
- P1-4: Wrap run_loop return in dict envelope

### Memory System
- MemoryRecord model with 6 typed memories + relevance/confidence scoring
- SQLite memories table with FTS5 full-text search + auto-sync triggers
- MemoryStore with CRUD, search, decay (0.95x/session), archive, recall
- MemoryExtractor: auto-extracts from evidence/verification with dedup
- DreamEngine: 4-phase consolidation (heuristics -> dedup -> merge -> prune)
- HeuristicEngine: generates reusable rules from 3+ recurring patterns
- CLI: `overmind memories` and `overmind dream`

## v2.0.0 Completed (2026-04-07, session 2)

### Feature 1: Runner Protocol Differentiation
- RunnerProtocol dataclass with INTERACTIVE/ONE_SHOT/PIPE instances
- Claude: interactive stdin, supports interventions
- Codex: one-shot stdin (close after prompt), no interventions
- Gemini: pipe mode with conciseness prompt prefix + decorative output filter
- Gemini capacity error detection ("too many people", "at capacity", etc.)
- Removed ONE_SHOT_STDIN_PATTERN regex from TerminalSession
- Protocol-aware intervention filtering in SessionManager

### Feature 2: DAG Task Dependencies
- `blocked_by: list[str]` field on TaskRecord
- TaskQueue.queued() filters blocked tasks (deps must be COMPLETED/ARCHIVED)

### Feature 3: Dry-Run Mode
- `overmind run-once --dry-run` previews dispatches without starting sessions
- Full pipeline runs (scan, generate, prioritize, schedule) but skips dispatch
- No task state transitions in dry-run mode

### Feature 4: Git Worktree Isolation
- WorktreeManager: create/cleanup/needs_isolation
- Creates `overmind/<task_id>` branches in isolated worktrees
- Config: `isolation.mode: worktree | none` in policies.yaml
- Non-git projects gracefully skipped

## Test Results
- **82/82 tests pass** (29 original + 24 memory + 29 v2)

## Stats
- Source: ~5,200 lines
- Tests: ~2,200 lines
- New modules: protocols.py, worktree_manager.py, extractor.py, dream_engine.py, heuristic_engine.py
