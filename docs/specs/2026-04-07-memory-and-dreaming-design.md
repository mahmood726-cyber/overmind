# Overmind v1.1 — Memory, Dreaming, and Bug Fixes

> Design spec for persistent cross-session memory, dreaming (memory consolidation),
> heuristic extraction, and all P0/P1 bug fixes from the v1.0 review.
>
> Date: 2026-04-07
> Status: APPROVED

## Context

Overmind v1.0 is a local orchestrator (3,910 lines, 29/29 tests) that supervises
Claude Code, Codex CLI, and Gemini CLI as terminal subprocesses. It scans ~276
projects, generates verification tasks, dispatches to runners, watches output for
loops/failures, and gates completion on independent verification.

The system operates within Mahmood's research pipeline:
- Three AI CLIs share synchronized instruction files (CLAUDE.md, AGENTS.md, GEMINI.md)
- All work flows through C:\E156 (micro-papers + GitHub repos + Pages dashboards)
- C:\ProjectIndex\INDEX.md is the master registry of 276+ repos
- Evidence-first, fail-closed, deterministic workflow with TruthCert proof-carrying numbers

### Problems to Solve

1. **No cross-session memory** — Each `run_once` tick starts fresh. Overmind forgets
   what it learned about projects, runners, and task strategies.
2. **No memory consolidation** — Even with memory, entries will accumulate noise,
   duplicates, and contradictions over time.
3. **7 bugs from review** — P0: package data missing, C:\ root scan, tuple length
   mismatch. P1: timeout handling, SQL safety, empty candidates crash, return type.
4. **Stub modules** — `runner_profiles.py`, `regression_log.py`, `summaries.py` are
   empty shells that should carry real functionality.

### Research Sources

- **Claude Dreaming** (Anthropic's unreleased autoDream): 4-phase consolidation
  (orient → gather → consolidate → prune). Community replications: Josue7211/claude-dream,
  grandamenium/dream-skill.
- **Mem0**: ADD/UPDATE/DELETE/NOOP conflict resolution pattern.
- **A-Mem** (NeurIPS 2025): Linked notes with metadata and bidirectional references.
- **Reflexion/ERL**: Automated heuristic extraction from failures/successes.
- **xMemory**: Hierarchical compression (raw → episodes → semantics → themes).
- **Composio AO**: Reaction engine, plugin slots, CI failure injection.
- **Overstory**: SQLite mailbox for inter-agent communication.
- **Claudio**: TripleShot competing agents, DAG task dependencies.
- **Codex Orchestrator**: Codebase map injection for context efficiency.

---

## Part 1: Bug Fixes

### P0-1: Package data for prompts
Add `[tool.setuptools.package-data]` to `pyproject.toml` so `overmind/prompts/*.txt`
is included in pip installs.

### P0-2: Remove C:\ from scan_roots
Remove `"C:\\"` from `config/roots.yaml`. The other roots already cover all project
directories. Scanning C:\ root wastes time and risks permission errors.

### P0-3: Consistent tuple lengths in _command_priority
In `project_scanner.py`, pad all return tuples to the same length (6 elements) so
comparisons never hit IndexError on ties.

### P1-1: Handle subprocess.TimeoutExpired in verifier
Wrap `subprocess.run()` in `verifier.py` with try/except for `TimeoutExpired`. On
timeout, mark the check as failed with a descriptive message, don't crash the tick.

### P1-2: SQL table name whitelist
Add `VALID_TABLES` set to `db.py`. Validate `table` parameter in `_upsert`, `_get`,
`_list` against the whitelist before interpolation.

### P1-3: Fix empty candidates in _last_active_timestamp
Guard `max()` call with an empty check. Return `None` if no candidates exist.

### P1-4: Wrap run_loop return in dict envelope
Change `run_loop` to return `{"iterations": [...]}` instead of a bare list, matching
the dict pattern used by all other CLI commands.

---

## Part 2: Memory System

### 2.1 Memory Record Model

```
MemoryRecord:
  memory_id: str          # "mem_{uuid8}"
  memory_type: str        # project_learning | runner_learning | task_pattern | decision | regression | heuristic
  scope: str              # project_id, runner_id, or "global"
  title: str              # Short summary (used in search/display)
  content: str            # Full memory text
  source_task_id: str?    # Task that generated this memory
  source_tick: int        # Which tick number
  relevance: float        # 0.0-1.0, decays each session
  confidence: float       # 0.0-1.0, boosted on confirmation
  tags: list[str]         # Searchable keywords
  linked_memories: list[str]  # IDs of related memories
  created_at: str
  updated_at: str
  status: str             # active | archived | merged
```

### 2.2 Storage: SQLite + FTS5

New `memories` table with full-text search index:

```sql
CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    memory_type TEXT NOT NULL,
    scope TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source_task_id TEXT,
    source_tick INTEGER DEFAULT 0,
    relevance REAL DEFAULT 1.0,
    confidence REAL DEFAULT 0.5,
    tags TEXT DEFAULT '[]',
    linked_memories TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT DEFAULT 'active'
);

CREATE VIRTUAL TABLE memories_fts USING fts5(
    title, content, tags,
    content='memories',
    content_rowid='rowid'
);
```

Search uses FTS5 keyword matching with scope/type filtering. No vector embeddings
needed at this scale (<10K memories).

### 2.3 MemoryStore (rewrite of existing stub)

```
class MemoryStore:
    save(memory: MemoryRecord) -> None
    search(query: str, scope: str?, memory_type: str?, limit: int = 10) -> list[MemoryRecord]
    recall_for_project(project_id: str, limit: int = 5) -> list[MemoryRecord]
    recall_for_runner(runner_id: str, limit: int = 5) -> list[MemoryRecord]
    recall_heuristics(task_type: str, limit: int = 5) -> list[MemoryRecord]
    decay_all(factor: float = 0.95) -> int  # returns count of decayed
    archive_stale(threshold: float = 0.1) -> int  # returns count archived
    update_relevance(memory_id: str, boost: float) -> None
    forget(memory_id: str) -> None
    list_all(status: str = "active", limit: int = 50) -> list[MemoryRecord]
    stats() -> dict  # counts by type, scope, status
```

### 2.4 MemoryExtractor (new module)

Runs after each `run_once` tick. Examines evidence and verification results to
extract typed memories:

| Signal | Memory Type | Example |
|--------|-------------|---------|
| Verification passed | project_learning | "PairwisePro: all 101 tests pass in 12s" |
| Verification failed | project_learning + regression | "prognostic-meta: hazard ratio edge case failed" |
| Loop detected | task_pattern | "browser_app tasks on codex loop after 3 retries" |
| Proof gap | task_pattern | "claude_main claims done without running tests" |
| Rate limit | runner_learning | "codex_local_a rate-limited at 11:52 PM" |
| Non-zero exit | runner_learning | "gemini_optional crashed on large prompt (>4K lines)" |
| Task completed | task_pattern | "verification tasks average 2 ticks to complete" |
| Task assigned to runner | decision | "assigned architecture task to claude (score 0.8)" |

Before saving, the extractor searches for existing memories with the same scope and
similar content. If found, it updates (boost relevance + merge content) instead of
creating a duplicate.

### 2.5 HeuristicEngine (new module)

Distills memories into reusable rules in the style of Reflexion/ERL:

```
Format: "When [situation], [strategy] works/fails because [reason]."
```

Runs during dreaming (not every tick). Scans recent memories of type
`project_learning`, `task_pattern`, and `regression`. Groups by scope. For each
group with 3+ memories showing a pattern, generates a `heuristic` memory.

Examples:
- "When running verification on browser_apps, the first tick assigns but the second
  tick completes. Allow 2 ticks before declaring failure."
- "When codex_local_a hits rate limit, gemini_optional is a viable fallback for
  non-architecture tasks."
- "When prognostic-meta tests fail, the bootstrap module is usually the cause.
  Run test_hazard_ratio.py first to isolate."

### 2.6 Memory Integration in Orchestrator

**Before dispatching** (`run_once`):
1. Load project memories for each task being assigned
2. Load runner memories for the assigned runner
3. Load relevant heuristics for the task type
4. Inject into worker prompt as a `PRIOR LEARNINGS` section

**After observing** (`run_once`):
1. Run `MemoryExtractor` on evidence + verification results
2. If existing memory confirmed (same learning re-observed), boost relevance

**On session start** (orchestrator `__init__`):
1. Run `decay_all(0.95)` to age all memories slightly
2. Run `archive_stale(0.1)` to archive memories below threshold

---

## Part 3: Dreaming (Memory Consolidation)

### 3.1 Dream Cycle

Four phases, inspired by Anthropic's autoDream:

**Phase 1: Orient**
- Count total active memories by type and scope
- Identify memory clusters (same scope, similar content)

**Phase 2: Gather**
- Collect all active memories sorted by relevance (descending)
- Group by scope (project_id, runner_id, global)

**Phase 3: Consolidate**
- **Deduplicate**: Memories with same scope + overlapping content → merge into one,
  combine tags, keep highest relevance/confidence, link back to originals
- **Resolve conflicts**: If two memories in same scope contradict (e.g., "tests take
  12s" vs "tests take 45s"), keep the newer one, archive the older with status=merged
- **Extract heuristics**: Run HeuristicEngine on the memory corpus
- **Compress**: Memories older than 30 days with relevance < 0.3 → archive

**Phase 4: Prune**
- Archive all memories with status=merged
- Delete archived memories older than 90 days
- Rebuild FTS5 index
- Log dream summary (memories before/after, merges, heuristics generated)

### 3.2 Dream Triggers

- **Manual**: `overmind dream` CLI command
- **Automatic**: After every 5th tick in `run_loop`, check if dreaming is needed.
  Conditions: 5+ ticks since last dream AND 10+ active memories exist.

### 3.3 Dream State

Persisted in the `checkpoints` table:
```json
{
  "last_dream_at": "2026-04-07T10:00:00+00:00",
  "ticks_since_dream": 0,
  "memories_before": 45,
  "memories_after": 32,
  "heuristics_generated": 3,
  "merges": 8,
  "archives": 5
}
```

---

## Part 4: CLI Commands

### New subcommands

```
overmind memories                     # List all active memories (summary view)
overmind memories --type heuristic    # Filter by type
overmind memories --scope <project>   # Filter by scope
overmind memories --search "bootstrap" # FTS5 search
overmind memories --forget <id>       # Delete a specific memory
overmind memories --stats             # Show counts by type/scope/status

overmind dream                        # Run dream cycle manually
overmind dream --dry-run              # Show what would change without applying
```

---

## Part 5: File Changes

### New files
| File | Purpose | Est. lines |
|------|---------|-----------|
| `overmind/memory/extractor.py` | Extract memories from evidence/verification | ~120 |
| `overmind/memory/heuristic_engine.py` | Distill memories into reusable rules | ~80 |
| `overmind/memory/dream_engine.py` | 4-phase consolidation cycle | ~150 |
| `tests/unit/test_memory_store.py` | Memory CRUD, search, decay, dedup | ~100 |
| `tests/unit/test_extractor.py` | Memory extraction from evidence | ~80 |
| `tests/unit/test_dream_engine.py` | Dream consolidation cycle | ~80 |
| `tests/unit/test_heuristic_engine.py` | Heuristic generation | ~60 |
| `tests/unit/test_bug_fixes.py` | Targeted tests for P0/P1 fixes | ~80 |

### Modified files
| File | Changes |
|------|---------|
| `pyproject.toml` | Add package-data for prompts |
| `config/roots.yaml` | Remove C:\ root |
| `overmind/storage/db.py` | Add memories table + FTS5, table name whitelist |
| `overmind/storage/models.py` | Add MemoryRecord dataclass |
| `overmind/memory/store.py` | Full rewrite: persist, search, decay, deduplicate |
| `overmind/memory/insights.py` | Wire to MemoryExtractor |
| `overmind/memory/runner_profiles.py` | Implement using memory queries |
| `overmind/memory/regression_log.py` | Implement using memory storage |
| `overmind/core/orchestrator.py` | Integrate memory recall + extraction into tick |
| `overmind/verification/verifier.py` | Handle TimeoutExpired |
| `overmind/discovery/project_scanner.py` | Fix tuple lengths + empty candidates |
| `overmind/cli.py` | Add memories + dream subcommands |

### Not changed (reserved for v2)
- Runner adapters (claude/codex/gemini differentiation)
- Vector embeddings / semantic search
- SQLite mailbox inter-agent communication
- TripleShot competing agents
- Codebase map injection
- External event reaction engine
- API server / dashboard

---

## Part 6: Testing Strategy

All new code tested with `pytest`. Target: 29 existing + ~25 new = ~54 tests.

| Test area | What's tested |
|-----------|---------------|
| Memory CRUD | Save, search, recall, forget, list, stats |
| FTS5 search | Keyword matching, scope filtering, type filtering |
| Decay + archive | Relevance decay, stale archiving, threshold behavior |
| Deduplication | Same-scope similar memories merge correctly |
| Memory extraction | Each evidence signal type produces correct memory type |
| Heuristic generation | Patterns with 3+ memories produce heuristics |
| Dream cycle | Full 4-phase: dedup → resolve → extract → prune |
| Bug fixes | Each P0/P1 fix has a targeted regression test |
| Integration | run_once tick produces memories, dream consolidates them |

---

## Success Criteria

1. All 29 existing tests still pass (no regressions)
2. All ~25 new tests pass
3. `overmind run-once` produces memories from verification evidence
4. `overmind memories` displays stored memories with search
5. `overmind dream` consolidates duplicates and generates heuristics
6. All 7 P0/P1 bugs fixed
7. Memory persists across process restarts (SQLite-backed)
