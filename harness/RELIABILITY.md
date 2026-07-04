# RELIABILITY — reliability-hardening workstream (scoped, additive, no-regression)

**Date:** 2026-07-04
**Scope:** close only the reliability gaps that remove a **real cost we actually hit today**, additive
and gated, sequenced so they don't conflict with the differentiator increments. Single writer; every
fix its own commit; no push to protected branches. New code lives in `overmind/reliability/` — a fresh
package **nothing imports yet**, so it cannot regress existing behavior (proven: full suite green).

**Priority = benchmark integrity first** (2,1,4,5,6), then 3 — an unreliable harness would corrupt the
very §3 benchmark run that is meant to prove best-in-class.

---

## What shipped (each justified by a failure we hit)

| # | Fix | Modules | Cost it removes | Tests |
|---|---|---|---|---|
| **2** | Truthful drain monitor | `reliability/drain_monitor.py` | the agent-drain-watchdog's **session-only blind spot** — a dead loop / capped seat read as "fine" (false negative). Now read from heartbeat files + cap-log (ground truth). | (with #1) |
| **1** | Supervised drain loops + cap-log | `reliability/{heartbeat,cap_log,supervised_loop}.py` | a drain loop **silently dying** or **busy-hammering a capped seat**; cap/reset times invisible until a session noticed. Now: heartbeat per loop, auto-restart, sleep-to-reset, one machine-readable cap-log. | +15 |
| **4** | Anti-wedge exec + ReDoS screen | `reliability/safe_exec.py` | a **runaway node/lint** and a **catastrophic-backtrack regex** wedging a session. Now: bounded timeout + process-tree kill + stdin=NUL; a ReDoS pre-screen fails a bad pattern closed. | +21 |
| **5** | F:/E: routing guard | `reliability/routing_guard.py` | the **daily-methods-paper + journal-lane failures** — F:/E: tasks routed to the Cowork sandbox that can't reach those drives. Now: rule encoded (F:/E: → F:-node CODE task, never sandbox). | +10 |
| **6** | Checkpoint/resume | `reliability/checkpoint.py` | **restarting a long run from zero** after a kill (esp. the benchmark). Now: per-loop atomic checkpoint; `remaining()` yields the resume worklist. | +11 |
| **3** | Truthful auth preflight | `reliability/auth_preflight.py`, `scripts/auth_preflight.py`, `harness/AUTH_PREFLIGHT_RUNBOOK.md` | `codex login status` **lying** (seat "logged in" but 401-revoked) → silent dispatch failure. Now: real `codex exec`/`agy --print` smoke; degraded seats never dispatched. | +8 |

**Total: +73 tests, all green. No existing module edited** (item 3 reuses the existing
`smoke_probe_codex_seats`; everything else is new files) → no regression by construction.

## Documented paths / flags
- **Cap-log (single machine-readable):** default `<data_dir>/reliability/cap_log.jsonl`, override
  `OVERMIND_CAP_LOG_PATH`. Records `{seat, cap_message, detected_at, reset_at}` per event; `reset_at`
  is the readable expected-clear time; `active_caps()` folds the stream.
- **Heartbeat files:** one `*.hb.json` per loop in a heartbeat dir the monitor globs; `{loop, status,
  updated_at, pid, iteration, detail}`; staleness = no beat within `stale_after_seconds` (default 15m).
- **Auth preflight:** `python scripts/auth_preflight.py` (exit 1 if all non-Claude vendors degraded).

## Adoption (next, still additive/gated — not done in this workstream)
These primitives are built + tested; wiring them into the live loops is the follow-on (each behind a
flag, shadow-first):
1. Have the external Dispatch drain loops write heartbeats + record caps via `SupervisedLoop`, and the
   orchestrator/monitor read `DrainReport` instead of session inspection (retire the session-only
   watchdog — item 2 recommendation).
2. Route lint/node/test launches through `safe_exec.run_guarded`; screen rule-authored regexes with
   `compile_guarded` at load time.
3. Call `routing_guard.assert_fs_routing` at the dispatch decision point.
4. Use `CheckpointStore` in the §3 benchmark runner (per-task checkpoint).
5. Run `auth_preflight.preflight_all` before any Codex/agy dispatch; feed degraded seats into the
   cross-vendor stage's `AUTH_DEGRADED` handling.

---

## Explicitly REJECTED (wastage / regression risk — recorded with reason)

| Rejected | Reason |
|---|---|
| **Heavyweight external orchestration framework (LangGraph / AutoGen / CrewAI / etc.)** | Adopting one to "match on paper" would be a large rip-and-replace of a working multiprocessing/Dispatch model — high regression risk, new dependency + failure surface, and it buys nothing the scoped primitives above don't: our control plane is Dispatch (`WORLD_CLASS_SPEC` §0.5), and the reliability gaps were substrate issues (wedge/auth/routing/resume), not a missing framework. **Cost of adopting > cost it removes.** |
| **Trained/learned memory-skill model built from scratch (AutoMem-style)** | AutoMem is a research *training* method (a distilled memory-skill model), not a drop-in. Building one is a large ML project orthogonal to today's costs. We keep the **evolving-memory PRINCIPLE** via the vault (human mirror) + MemClaw (machine mirror) in **shadow only** — mirror existing state files additively, files stay source of truth. No trained model. |
| **Any formal execution-graph engine** (SGH DAG scheduler, durable-execution runtime like Temporal/DBOS) beyond the minimal checkpoint | The only resume cost we hit is "long run restarts from zero" — closed by item 6's per-loop checkpoint (a state file, ~120 LoC). A full DAG/durable-execution engine is an unvalidated (SGH is a position paper) or heavyweight rewrite with real regression risk. Revisit only if a measured need appears that the checkpoint can't meet. |

**Principle applied:** close a gap only when the fix's cost is clearly less than the recurring cost it
removes, and only for costs we have actually paid. Everything heavier is deferred behind a measured need.
