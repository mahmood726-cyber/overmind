# Overmind v0.2.0 Progress

## Completed (2026-04-07)

### Bug Fixes (7/7)
- P0-1: Package data for prompts/*.txt (pyproject.toml)
- P0-2: Removed C:\ from scan_roots
- P0-3: Consistent 6-element tuples in _command_priority
- P1-1: Handle subprocess.TimeoutExpired in verifier (Popen + kill)
- P1-2: SQL table name whitelist in db.py
- P1-3: Guard _last_active_timestamp against empty candidates + OSError
- P1-4: Wrap run_loop return in dict envelope

### Memory System
- MemoryRecord model with 6 memory types + relevance/confidence scoring
- SQLite memories table with FTS5 full-text search + auto-sync triggers
- MemoryStore: full CRUD, search, decay (0.95x/session), archive (< 0.1), recall
- MemoryExtractor: auto-extracts typed memories from evidence/verification results
  - project_learning, runner_learning, task_pattern, decision, regression, heuristic
  - Deduplicates: boosts relevance instead of creating duplicate entries

### Dreaming (Memory Consolidation)
- DreamEngine: 4-phase cycle (extract heuristics -> consolidate -> prune)
- HeuristicEngine: generates reusable rules from 3+ recurring patterns
- Auto-triggers after 5 ticks with 10+ active memories
- Manual trigger: `overmind dream` CLI command

### Integration
- Memory recall injected into worker prompts as PRIOR LEARNINGS section
- Decay + archive runs on orchestrator init (session start)
- Memory extraction runs after every run_once tick
- Dream check after every tick

### CLI
- `overmind memories` (list, --type, --scope, --search, --forget, --stats)
- `overmind dream` (--dry-run)

## Test Results
- **53/53 tests pass** (29 existing + 24 new)
- New test files: test_bug_fixes.py, test_memory_store.py, test_extractor.py, test_dream_engine.py

## Stats
- Source: ~4,600 lines (was 3,910)
- Tests: ~1,750 lines (was 1,252)
- New files: 3 modules + 4 test files + 1 spec + 1 plan
