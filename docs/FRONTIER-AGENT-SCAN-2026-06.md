# Frontier Agent Scan — June 2026

**Purpose:** Map recent AI-agent developments + the user's Tower repo to concrete, prioritised
upgrades for Sentinel/Overmind (`F:\overmind`).
**Truth-first policy:** Every claim about what Overmind *does or does not have* was verified
by direct read of source files listed. MRAgent and external-research sections are explicitly
marked PENDING where results were not yet received from the web-fetch agent at commit time.

---

## Sources

| ID | Source | Verified? |
|----|--------|-----------|
| A | MRAgent (Ji-shuo/MRAgent, GitHub) | PENDING — web-fetch agent not yet returned; section placeholder below |
| B | Recent AI-agent developments 2025-2026 | PENDING — research agent not yet returned |
| C | Tower repo (`F:\Tower`, also `mahmood726-cyber/tower` on GitHub) | YES — read locally + GitHub scan |
| D | "Loop Engineering: The Anatomy of an Autonomous Loop" (zostaff, Jun 2026) | YES — full text provided by user; mapped against Overmind direct reads |

---

## Source A — MRAgent (Ji-shuo/MRAgent)

> **STATUS: PENDING.** The web-fetch agent launched to retrieve the README and key source files
> from `https://github.com/Ji-shuo/MRAgent` had not returned results at commit time.
> This section will be updated when the agent completes.
>
> **Known context (from user brief):** MRAgent automates Mendelian Randomization (MR) research
> — hypothesis generation → data retrieval → statistical analysis → write-up, orchestrated by
> an LLM planner. It is relevant because the same planning → tool-use → verification loop
> pattern applies directly to Overmind's portfolio-verification pipeline.

---

## Source B — Recent AI-Agent Developments (2025-2026)

> **STATUS: PENDING.** The research agent covering web searches on automated meta-analysis
> agents, self-verifying critics, multi-agent debate, tool-augmented reasoning, and
> reproducibility agents had not returned results at commit time.
> This section will be updated when the agent completes.

---

## Source C — Tower Repo (`F:\Tower`)

Tower is the user's own multi-language build/deploy/verification infrastructure for ~26
evidence-synthesis projects. Studied via: local file read + GitHub API scan of
`mahmood726-cyber/tower`. Architecture is in `ARCHITECTURE.md` (v1.5.7), `SPEC.md`,
`addons/autoclaude/` (23 files), `scripts/` (30+ files), and `addons/` plugin tree.

### C.1 What Tower does

| Layer | Key component | Description |
|-------|--------------|-------------|
| Workflow | `tower-cli` (757 lines) | Card-based CLI: `tower new/run/check/pack/merge`. Cards = CARD-NNN work units with lifecycle ACTIVE→GATED→GOLD→MERGED |
| Run provenance | `scripts/tower_run.sh` | Every command wrapped with `run_context.json` + stdout/stderr logs + heartbeat ping every 60s + `run_summary.json` on exit. Atomic writes via temp-then-rename |
| Verification | `scripts/tower_gatecheck.sh` | VALIDATE → ANALYZE → CORRECT → VERIFY self-correcting loop. Emits GREEN/YELLOW/RED into `control/status.json`. P0 = tests+validators; P1 = proofpack |
| Night batch | `scripts/night_runner.sh` | Processes a JSON queue only 22:00–06:00 UTC; allowlist of safe commands only; dry-run mode |
| Multi-agent | `addons/autoclaude/agent_orchestrator.py` (793 lines) | 5 patterns: Supervisor, Coordinator-Worker, Blackboard, Pipeline, Hierarchical. `AgentRouter` (best_match/round_robin/cost_optimized), `TaskDecomposer`, `ResultAggregator` (vote/merge/concat) |
| Circuit breaker | `addons/autoclaude/circuit_breaker.py` | CLOSED→OPEN→HALF_OPEN state machine. Trips after N failures; persisted to `control/circuit_states.json`. Escalation callback at 2×threshold |
| Confidence scoring | `addons/autoclaude/confidence_scorer.py` | Multi-heuristic (completion quality, structure, uncertainty markers, consistency, length). Thresholds: HIGH>0.8 auto-proceed, VERY_LOW<0.3 reject/escalate. Calibrated via Brier score |
| LLM cost tracking | `addons/autoclaude/llm_tracker.py` | Per-call JSONL log with model, tokens, cost_usd, latency_ms, card_id. Budget enforcement (daily/monthly/per-card). BudgetExceededError before call |
| Human gates | `addons/autoclaude/human_checkpoint.py` | PENDING→APPROVED/REJECTED/MODIFIED/TIMEOUT state machine. Risk-based: LOW=auto-approve, CRITICAL=multiple approvers. Timeout + escalation chain |
| Decision explainer | `addons/autoclaude/decision_explainer.py` | Decision tree: factors, weights, directions, alternatives-rejected, reasoning narrative. Nested (portfolio→package→check). Human-readable audit trail |
| Evidence spec | `SPEC.md` (TruthCert/Burhan) | 7 Straight-Path Rules, 3 assurance badges (Bronze/Silver/Gold), isnad-style witness grading (Grade A = registry table, B = SR extract, C = inferred), quorum voting rules Q1/Q2/Q3, drift ledger |
| Event ledger | `addons/ledger/event_logger.py` | Append-only hash-chained JSONL (SHA-256 per event, links prev_hash). Cross-platform file locking (msvcrt/fcntl). Rotation at 10MB. Supports query helpers |
| SLO monitoring | `addons/slo/compute_slo.py` | Reads event ledger to compute rollback_rate, validator_fail_rate, drift_incidents/100h. SPC control charts. Breach alerting |

### C.2 What Tower has that Overmind currently lacks

Verified by cross-checking against Overmind source files:

| Tower component | Overmind status | Gap |
|----------------|-----------------|-----|
| `circuit_breaker.py` — CLOSED/OPEN/HALF_OPEN | **MISSING** | No same-agent or same-tool repeat detection in Overmind |
| `llm_tracker.py` — USD budget ceiling | **MISSING** | No per-run cost cap. `PROJECT_WORKER_TIMEOUTS` is wall-clock only |
| `human_checkpoint.py` — comprehension-debt gate | **MISSING** | No mandatory human-read gate that the nightly loop cannot skip |
| `confidence_scorer.py` — multi-heuristic calibration | PARTIAL | RoutedJudge has `escalate_below` / `pass_floor` thresholds but no Brier-score recalibration |
| `agent_orchestrator.py` Blackboard pattern | PARTIAL | QuorumJudge runs backends independently with no shared state between rounds |
| Event ledger (hash-chained JSONL) | PARTIAL | CertBundle has SHA-256 `bundle_hash` + Ed25519/HMAC signing, but no hash-chained *sequence* across projects |
| `night_runner.sh` time-window + safe allowlist | PARTIAL | Nightly runner has per-project worker timeouts but no time-window restriction or action allowlist for AutoFixer |
| `tower_run.sh` heartbeat ping every 60s | PARTIAL | `nightly_started_*.flag` written once at start; `SessionTracker.heartbeat()` exists but not called during `_verify_with_timeout` |
| TruthCert isnad witness-grading (A/B/C tiers) | PARTIAL | Overmind has `witness_type` (test_suite/smoke/numerical/semgrep) but no credibility grade — all witnesses are equally weighted |

### C.3 Transferable ideas (Tower → Overmind)

**C3-1 Circuit breaker for the auto-fix loop**
Sketch: Add `CircuitBreaker` (ported or re-implemented from `F:\Tower\addons\autoclaude\circuit_breaker.py`)
to `overmind/verification/`. Wire into `_run_verification()` (`nightly/runner.py:716-742`): if
`LLMRepairer.attempt_repair` fails for the same project 3 consecutive nights, trip the circuit
and log to `STUCK_FAILURES.jsonl` instead of re-attempting. State persisted to
`data/circuit_states.json`.

**C3-2 USD budget ceiling**
Sketch: Port `llm_tracker.py` pattern to `overmind/nightly/runner.py`. Add `--budget-usd` CLI
flag. Track cumulative cost in `run_state.cost_usd`; after each LLMRepairer/upgrade_unknown call
add `(prompt_tokens/1M * price_in + completion_tokens/1M * price_out)`. Halt with warning if
ceiling exceeded.

**C3-3 Hash-chained evidence ledger**
Sketch: In `overmind/nightly/reporting.py`, after writing each `bundle_path` JSON, append an
event to `data/evidence_ledger.jsonl` — `{id, timestamp, project_id, verdict, bundle_hash, prev_hash}`.
SHA-256 the canonical event (excluding prev_hash field) and chain. Enables cross-project
audit trail and tamper detection beyond individual bundle signatures.

**C3-4 Human checkpoint gate**
Sketch: In `nightly/runner.py`, after the auto-fix phase, if `failed + rejected > ESCALATION_THRESHOLD`
(e.g. 5) write a `data/human_review_queue.json` with the failing projects and their diagnoses.
Add `scripts/morning_gate.py` that reads the queue and requires explicit `--approve-and-continue`
before the wiki/skill-library updates publish. This is the "comprehension debt" gate.

**C3-5 Heartbeat during long verifications**
Sketch: In `_verify_with_timeout()` (`nightly/runner.py:74-201`), the existing poll loop
(`while worker.is_alive() and time.time() < deadline: time.sleep(2)`) already runs every 2s —
add a single line to write a liveness timestamp to `data/heartbeat_{project_id}.json` every
60s inside that loop. A morning health-check script can then detect silence > 90s as a hung
project.

**C3-6 Action allowlist for AutoFixer**
Sketch: In `nightly/runner.py:666-743`, add `SAFE_FIX_ACTIONS = frozenset({"BASELINE_UPDATE",
"FLOAT_PRECISION", "FORMULA_ERROR"})`. Skip `attempt_fix` and `attempt_repair` calls for
`diag.failure_type not in SAFE_FIX_ACTIONS` during scheduled nightly runs. `--unsafe-fixes`
flag re-enables. Mirrors `night_runner.sh`'s allowlist approach.

---

## Source D — "Loop Engineering: The Anatomy of an Autonomous Loop" (zostaff, Jun 2026)

Full mapping of every principle against Overmind, verified by direct source reads.

### Loop Anatomy: 5 parts — find work / plan / act / VERIFY / MEMORY

The article's central claim: only **verify** and **memory** (and the stop condition inside
verify) decide whether an autonomous loop succeeds. The other three parts are table stakes.
Mapping follows.

---

### Principle 1 — Independent verification (maker must NOT grade itself)

> Use a separate, often stronger/higher-reasoning model as adversarial checker.

**Overmind status: PARTIAL**

**What exists:**
- `overmind/verification/llm_judge.py`: `QuorumJudge` runs 2+ backends (Anthropic subprocess
  + Gemini API). `RoutedJudge` escalates cheap→expensive based on confidence thresholds
  (`escalate_below=0.75`, `pass_floor=0.85` for PASS, `llm_judge.py:679-693`).
- `overmind/verification/judge_factory.py:68-193`: `enforce_different_family()` is ON by
  default (`OVERMIND_JUDGE_QUORUM_ENFORCE`). Same-family judges are dropped from the panel;
  `effective_votes` < `nominal_votes` flagged as `quorum_correlated_panel`.
- Degenerate output guard (`arXiv:2507.08794`): empty / filler / punctuation-only responses
  abstain (`degenerate_response_reason()`, `llm_judge.py:451-475`).
- Injection / planted-verdict guard: asymmetric — coerced PASS rejected, genuine FAIL left
  intact (`injection_tamper_reason()`, `llm_judge.py:498-519`).
- CoT rubric prompt with truth-first rules (`OVERMIND_JUDGE_COT=1` default, `llm_judge.py:214-256`).

**Gap:**
The `SubprocessBackend` calls `claude -p` (same family as the maker runner). When the quorum
only has one non-claude backend available (e.g. Gemini key missing), the effective judge is
the same model family as the maker. No enforcement that the "expensive" tier in `RoutedJudge`
must be a *different* family from the maker, only that it is more expensive within the
configured set.

**Implementation sketch (S effort):**
In `judge_factory.py:265-282`, after `build_judge()` for the cheap tier, assert that
`family_for_engine(cheap_engine) != family_for_engine(maker_engine)` — where `maker_engine`
is read from `OVERMIND_MAKER_ENGINE` env var (default `claude`). Log a `maker_judge_same_family`
concern to the quorum verdict when this check fails. Wire `maker_engine` into `build_judge()`
signature.

---

### Principle 2 — `/goal` vs `/loop` (stop condition judged by a separate model)

> Run until a condition is *provably true*, judged by a separate small model via a Stop hook
> returning yes/no+reason. "No" is fed back as guidance.

**Overmind status: MISSING**

**What exists:**
- `overmind/activation/hooks/on_session_stop.py`: Stop hook exists but triggers memory
  extraction + dreaming, not goal-state checking. It does not evaluate whether a run goal
  was achieved.
- The nightly runner has a fixed project list — it runs all selected projects unconditionally.
  There is no "run until the portfolio is green" re-entry loop.

**Gap:**
No stop-condition model. No goal-state file. No "was the goal provably achieved?" check at
loop iteration end. The current model is batch-not-loop.

**Implementation sketch (M effort):**
1. Add `data/loop_goal.json`: `{goal: "all tier-3 projects CERTIFIED", fixpoint_check: "SELECT count(*) FROM bundles WHERE verdict != 'CERTIFIED' AND risk='high'", max_iterations: 3}`.
2. Add `overmind/activation/goal_checker.py`: lightweight class that queries the DB and runs a
   cheap LLM call (Haiku via `SubprocessBackend`) with prompt: *"Given goal: {goal}. Current
   state: {stats}. Is the goal provably met? Reply YES or NO with one-sentence reason."*
3. Wire into `on_session_stop.py`: if goal file exists, call `GoalChecker.check()`. If NO,
   emit the reason as context for the next session start hook.
4. Wire into `nightly/runner.py:main()`: if `--loop-mode` flag, re-invoke the verification
   pass up to `max_iterations` while goal not met.

---

### Principle 3 — Memory on disk, not in context

> STATUS.md with Done / In-progress / Next / NEVER-touch, read first + written last each
> iteration. Fresh context per iteration; state pulled from files.

**Overmind status: PARTIAL**

**What exists:**
- `overmind/memory/store.py`: SQLite-backed MemoryStore with `save()` / `search()` / `decay_all()`.
  Memory persists across runs (regression, heuristic, runner_learning types). Decay rates
  per type (`bundle_failure` decays at 0.85/tick; `feedback` at 0.99).
- `nightly/runner.py:309-363`: `nightly_started_*.flag` written atomically at run start.
  `.progress_{date}.json` written after each project (crash-resume). These are disk-backed
  state.
- `on_session_stop.py`: triggers `DreamEngine.dream()` (memory consolidation) on session end.

**Gap:**
No human-readable `STATUS.md` with Done/In-progress/Next/NEVER-touch sections per project.
Memory is queried via search API, not "read first" at the top of each iteration. Context
within a nightly run is not "fresh" — the runner holds the full project list in memory across
the loop. No per-project `NEVER-touch` guard.

**Implementation sketch (S effort):**
In `overmind/nightly/reporting.py`, add `write_status_md(projects, results, date_str)` that
emits `data/STATUS_{date}.md`:
```
## Done
- projectA CERTIFIED [bundle_hash]
## In progress
- projectB (running since 02:14 UTC)
## Next
- projectC, projectD
## NEVER-touch
- [from SKIP_PROJECTS in nightly/selection.py]
```
Call it after each project (alongside `_promote_progress_to_partial_report`). The next
session's start hook reads this file and injects it into the context.

---

### Principle 4 — Maker/checker separation (fast cheap + slow strict)

> Spend the second opinion where being wrong is expensive.

**Overmind status: HAVE**

- `RoutedJudge` (`llm_judge.py:651-712`): cheap judge first; escalate when
  `confidence < escalate_below=0.75`, or when PASS but `confidence < pass_floor=0.85`.
  Truth-first asymmetry: PASS is harder to trust (reward-hacking hides there), so PASS requires
  the higher `pass_floor` threshold to avoid escalation.
- `QuorumJudge` (`llm_judge.py:542-645`): multi-vendor cross-check with effective-votes
  accounting for correlated panels.

No gap. Principle 4 is implemented.

---

### Principle 5 — BRAKES BEFORE HORSEPOWER

> Step cap / budget ceiling (USD/phase) / blast radius / circuit breaker / liveness heartbeat.
> The cautionary case: an unbraked 2-agent loop ran 11 days and burned tens of thousands.

**Overmind status: PARTIAL — this is the highest-priority gap.**

| Brake | Overmind status | File / evidence |
|-------|-----------------|-----------------|
| **Step cap** (max iterations) | PARTIAL | `--limit N` caps project count; `LLM repair capped at 5 calls` (`runner.py:724`). But no max-retries-per-project across nightly runs. |
| **Budget ceiling (USD/phase)** | MISSING | `PROJECT_WORKER_TIMEOUTS` is wall-clock only. No token/cost accounting anywhere. |
| **Blast radius** (isolated worktree/container) | PARTIAL | `WorktreeManager` (`isolation/worktree_manager.py`) creates `git worktree` per task, but only activated when `needs_isolation()` is True (concurrent same-path projects). AutoFixer writes directly to project paths with no worktree. |
| **Circuit breaker** (same tool+args 3× → halt) | MISSING | No detection of repeated identical repair attempts. A failing auto-fix runs every nightly until manually cleared. |
| **Liveness heartbeat** (silence = died) | PARTIAL | `nightly_started_*.flag` written once. `SessionTracker.heartbeat()` exists but is NOT called inside `_verify_with_timeout`'s poll loop. |

**Implementation sketch — circuit breaker (S effort, highest priority):**
Add `overmind/verification/loop_brakes.py`:
```python
class CircuitBreaker:
    """Trips after N consecutive same-failure nights for a project."""
    def __init__(self, state_path: Path, threshold: int = 3): ...
    def record_attempt(self, project_id: str, failure_type: str) -> None: ...
    def is_open(self, project_id: str) -> bool: ...
    def reset(self, project_id: str) -> None: ...
```
In `_run_verification()` (`runner.py:400`), before `_verify_with_timeout()`: if
`circuit_breaker.is_open(proj.project_id)`, skip and log `SKIP (circuit open)`.
After verify: if verdict FAIL with same `failure_class` as prior run, `record_attempt()`.
State persisted to `data/circuit_states.json`.

**Implementation sketch — USD budget (S effort):**
Add `--budget-usd FLOAT` to `parse_args()`. Track running total in `_run_verification()`:
after each `upgrade_unknown_diagnosis` / `attempt_repair` call, add estimated cost
(`prompt_tokens / 1M * 3.0 + completion_tokens / 1M * 15.0` for claude-sonnet baseline).
If total > budget, skip remaining LLM calls and log to report.

**Implementation sketch — AutoFixer blast radius (S effort):**
In `auto_fixer.py`, require that all writes go through a `WorktreeManager`-managed path.
If the project has no `.git` dir, skip auto-fix (already partially gated by `risk_checker`).
Add `OVERMIND_AUTOFIXER_WORKTREE=1` env flag to enforce this.

**Implementation sketch — liveness heartbeat (S effort):**
Inside `_verify_with_timeout()` (`runner.py:93-95`), the poll loop already runs every 2s.
Add: `if int(time.time()) % 60 == 0: _atomic_write_text(heartbeat_path, json.dumps({...}))`.
A `scripts/morning_healthcheck.py` greps for stale heartbeats (> 90s silence) and pages.

---

### Principle 6 — Four Deaths

> Runaway (cap+budget) / silent death (heartbeat + fresh context) / random walk (hard fixpoint)
> / comprehension debt (mandatory human-read gate the loop cannot skip).

| Death | Overmind status |
|-------|-----------------|
| **Runaway** | PARTIAL — per-project wall-clock timeout (`_verify_with_timeout`); psutil process-tree kill (`runner.py:104-120`). Missing: total run budget cap. |
| **Silent death** | PARTIAL — `nightly_started` flag + `.progress_*.json` crash-resume. Missing: per-project liveness heartbeat during execution. |
| **Random walk** | PARTIAL — CERTIFIED requires test_suite + smoke + (for tier-3) numerical witnesses all PASS. Missing: explicit per-project fixpoint definition (e.g. "green tests AND baseline within tolerance"). |
| **Comprehension debt** | **MISSING** — No mandatory human-read gate anywhere in the nightly loop. DECISIONS.md is written to project repos but the loop never pauses for a human to read it. |

**Implementation sketch — comprehension debt gate (M effort):**
In `_run_verification()`, after the diagnosis/auto-fix phase, if
`len(diagnoses) > COMPREHENSION_THRESHOLD` (default: 3 consecutive nights with unresolved
FAIL/REJECT in the same projects), write `data/HOLD_FOR_HUMAN.md` listing the projects and
halt the wiki/skill-library promotion phase until a human runs `overmind check --ack-hold`.
This gate cannot be skipped by the nightly scheduler — it is a blocking file check.

---

### Principle 7 — Order: prove manual → fold to skill → wrap in loop → schedule

**Overmind status: PARTIAL**

**What exists:**
- `overmind/evolution/skill_library.py`: `promote_recipe()` promotes proven `FixRecipe` objects
  to `SKILLS.json`. `PromotionGate.sweep()` gates on evidence bundles.
- `nightly/runner.py:770-797`: recipes promoted, stale skills demoted — but driven by
  automated criteria, not the manual-first order.

**Gap:**
No enforcement that a fix was validated in at least one manually-triggered run before being
promoted to a scheduled skill. The scheduler can promote a recipe that was only ever tested
in automated nightly runs.

**Implementation sketch (S effort):**
In `PromotionGate` (`evolution/promotion.py`), add a `manual_run_required=True` flag. A recipe
is only eligible if `recipe.verified_in_manual_run is True`. Set this flag when the nightly
is invoked with `--manual` (an explicit human-initiated run), not when triggered by the
Windows Task Scheduler.

---

## Consolidated Findings Table

| # | Source | What it is | Transferable idea | Overmind mapping | Have? | Effort | Benefit |
|---|--------|-----------|-------------------|-----------------|-------|--------|---------|
| 1 | Tower C3-1 | Circuit breaker (CLOSED/OPEN/HALF-OPEN) | Stop retrying a broken project after N nights | `AutoFixer` + `LLMRepairer` in `nightly/runner.py:666-742` | MISSING | S | Prevents runaway auto-fix; addresses Loop Engineering Death #1 |
| 2 | Loop-D P5 | Budget ceiling (USD/phase) | Add `--budget-usd` flag; estimate token cost per LLM call | `nightly/runner.py` LLM repair phase | MISSING | S | Caps runaway cost; addresses Death #1 |
| 3 | Loop-D P5 | Liveness heartbeat | Write liveness file every 60s inside `_verify_with_timeout` | `nightly/runner.py:93-95` poll loop | PARTIAL | S | Detects silent death; addresses Death #2 |
| 4 | Loop-D P5 | AutoFixer blast radius | Require worktree isolation for all auto-fix writes | `auto_fixer.py`, `isolation/worktree_manager.py` | PARTIAL | S | Limits blast radius to isolated branch |
| 5 | Tower C3-6 | Night-runner action allowlist | Restrict auto-fix to `SAFE_FIX_ACTIONS` frozenset | `nightly/runner.py:666` | PARTIAL | S | Prevents non-safe actions during scheduled runs |
| 6 | Loop-D P3 | STATUS.md per iteration | Write human-readable Done/In-progress/Next/NEVER-touch after each project | `nightly/reporting.py` | MISSING | S | Enables fresh-context re-entry; addresses Death #2 |
| 7 | Loop-D P7 | Manual-run gate before skill promotion | Block recipe promotion unless validated in a manual run | `evolution/promotion.py` | PARTIAL | S | Enforces prove-then-automate order |
| 8 | Loop-D P1 | Maker/judge cross-family enforcement | Assert maker engine ≠ judge family in `judge_factory.py` | `judge_factory.py:265-282` | PARTIAL | S | Closes remaining self-grading gap |
| 9 | Tower C3-4 | Human comprehension-debt gate | Block wiki/skill updates until human acks repeated failures | `nightly/runner.py` post-fix phase | MISSING | M | Prevents shipping unread failure cascades; Death #4 |
| 10 | Loop-D P2 | Goal-directed stop condition | `GoalChecker` + `loop_goal.json`; Haiku model returns yes/no+reason | `activation/hooks/on_session_stop.py` | MISSING | M | Converts batch→loop; enables provable completion |
| 11 | Tower C3-3 | Hash-chained evidence ledger | Append cross-project `evidence_ledger.jsonl` with prev_hash | `nightly/reporting.py` after each bundle | PARTIAL | M | Full audit trail across projects; tamper detection |
| 12 | Tower C3-5 | Agent capability model + routing | Route verifications by `quality_score / latency` per judge | `verification/judge_factory.py` + `runners/q_router.py` | PARTIAL | M | Cost-optimized multi-judge dispatch |
| 13 | Tower SPEC | Witness grading (A/B/C tiers) | Grade witnesses by credibility (A=human/baseline, B=automated, C=inferred) | `verification/scope_lock.py`, `cert_bundle.py` | PARTIAL | M | Finer verdict calibration than binary pass/fail |
| 14 | Tower Orchestrator | Blackboard shared-state for quorum | Let QuorumJudge backends share prior findings before final vote | `verification/llm_judge.py:542-645` | MISSING | L | Judges inform each other; reduces decorrelated disagreement |
| 15 | Tower SLO | Verification SLO monitoring | Track judge accuracy, consensus rate, latency SLOs as metrics | `nightly/reporting.py` + new `verification/slo.py` | MISSING | L | First-class observability for verification health |

---

## Prioritised Adoption Shortlist

### Top 5 Quick Wins (effort S, ≤1 day each)

**QW-1 — Circuit breaker for auto-fix (Tower C3-1 + Loop-D P5 "runaway")**
What: CLOSED/OPEN/HALF-OPEN state machine, tripped after 3 consecutive FAIL nights for same
project+failure_type.
Idea: Stop wasting nightly LLM budget on unfixable projects; surface them in `STUCK_FAILURES.md`.
Module: New `overmind/verification/loop_brakes.py`; wire into `nightly/runner.py:400` (before
`_verify_with_timeout`) and `runner.py:716` (after diagnose, before AutoFixer call).
Evidence: `F:\Tower\addons\autoclaude\circuit_breaker.py` (state machine + persistence pattern).

**QW-2 — USD budget ceiling (Loop-D P5 "budget ceiling")**
What: `--budget-usd FLOAT` flag; track cumulative LLM cost in nightly run; halt when exceeded.
Idea: The only protection today is wall-clock timeout. A tight loop of cheap calls can burn
hundreds of calls before the process-timeout fires.
Module: `nightly/runner.py:parse_args()` + running `run_state.cost_usd` accumulator.
Evidence: `F:\Tower\addons\autoclaude\llm_tracker.py` (cost calculation pattern).

**QW-3 — Liveness heartbeat during verification (Loop-D P5 + Death #2)**
What: Every 60s inside `_verify_with_timeout`'s poll loop, write
`data/heartbeat_{project_id}.json` with `{ts, project, pid}`. Morning health-check greps
for stale (> 90s) entries.
Module: `nightly/runner.py:93-95` (2 lines inside existing poll loop).
Evidence: Verified no such write exists. `nightly_started_*.flag` is written once at start only.

**QW-4 — AutoFixer action allowlist (Tower C3-6 + Loop-D P5 "blast radius")**
What: Restrict scheduled nightly auto-fix to `SAFE_FIX_ACTIONS = {"BASELINE_UPDATE",
"FLOAT_PRECISION", "FORMULA_ERROR"}`. Everything else deferred to manual `--unsafe-fixes` run.
Module: `nightly/runner.py:666` before `auto_fixer.attempt_fix()`.
Evidence: Current code has no action allowlist; `LLMRepairer` cap is 5 calls per run but
covers any `failure_type` including destructive ones.

**QW-5 — STATUS.md per-iteration (Loop-D P3 "memory on disk")**
What: After each project's bundle is written, append to `data/STATUS_{date}.md` with Done /
In-progress / Next / NEVER-touch sections (readable by the next session's start hook).
Module: `nightly/reporting.py` — new `write_status_md()` called alongside
`_promote_progress_to_partial_report()`.
Evidence: Verified no such file exists. `.progress_*.json` is machine-readable only.

---

### Top 3 Bigger Bets (effort M, ≤1 week each)

**BB-1 — Human comprehension-debt gate (Loop-D P6 Death #4 + Tower human_checkpoint.py)**
What: After diagnosis/auto-fix phase, if the same projects have been FAIL/REJECT for ≥ 3
consecutive nights, write `data/HOLD_FOR_HUMAN.md` and block wiki/skill-library updates
until `overmind check --ack-hold` is run explicitly. The loop **cannot** skip this gate.
Modules: `nightly/runner.py` post-fix phase (write gate file); `evolution/promotion.py` /
`evolution/skill_library.py` (check gate file before promoting).
Why: The article names this the most under-taught brake. A loop that self-repairs can
accumulate "comprehension debt" — silently promoting bad fixes until the problem is too
large to review.

**BB-2 — Goal-directed stop condition (Loop-D P2)**
What: `data/loop_goal.json` defines the fixpoint (e.g. "all high-risk projects CERTIFIED").
`GoalChecker` in `overmind/activation/goal_checker.py` uses a cheap Haiku model call to
evaluate yes/no+reason at the end of each nightly run. When no=yes, the reason is injected
as context for the next run's start hook.
Modules: New `overmind/activation/goal_checker.py`; `activation/hooks/on_session_stop.py`;
`nightly/runner.py:main()` with `--loop-mode` flag.
Why: Converts Overmind from batch ("run all projects once") to loop ("run until goal met").
This is the architectural step that enables fully autonomous verification campaigns.

**BB-3 — Hash-chained evidence ledger (Tower SPEC/ledger + Loop-D P3 "memory")**
What: In `nightly/reporting.py`, after each bundle is written, append to
`data/evidence_ledger.jsonl` with `{id, ts, project_id, verdict, bundle_hash, prev_hash}`
where `prev_hash = SHA256(prior event)`. This creates an append-only tamper-evident chain
across the entire portfolio across time.
Modules: `nightly/reporting.py`; new `verification/evidence_ledger.py`.
Why: CertBundle signing already proves individual bundle integrity, but there is no proof
that the *sequence* of verdicts (CERTIFIED → FAIL → CERTIFIED) is complete and unmodified.
The ledger closes this gap and enables SLO queries ("what was the false-positive rate last
30 days?").

---

## What to do next

1. **Immediate (today):** Implement QW-1 (circuit breaker) + QW-3 (heartbeat) — both are
   ≤ 30 lines each and address the two highest-risk failure modes (runaway + silent death).
2. **This week:** QW-2 (budget ceiling) + QW-4 (action allowlist) + QW-5 (STATUS.md).
3. **Next sprint:** BB-1 (comprehension-debt gate) — this is the hardest brake to add
   because it crosses the loop/schedule boundary.
4. **Update this doc** when the MRAgent (Source A) and external-research (Source B) agents
   return their results.
