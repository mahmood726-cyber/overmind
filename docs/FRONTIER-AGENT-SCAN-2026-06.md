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
| E | "Loop Engineering" — incremental patterns (Raytar, Jun 2026) | YES — full principles provided by user; incremental additions only (no duplication of article D) |
| F | "Vector RAG Isn't Enough — I Built a Context Graph Layer for Multi-Agent Memory" (Emmimal P Alexander, TDS, Jun 2026; repo github.com/Emmimal/context-graph-benchmark) | YES — key findings and numbers provided by user verbatim; Overmind memory layer verified by direct reads of `storage/models.py`, `memory/store.py`, `verification/claim_graph.py`, `storage/db.py`, `intelligence/portfolio_state.py` |

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

## Source E — "Loop Engineering" — incremental patterns (Raytar, Jun 2026)

Full text provided by user. This section covers only patterns **not already in Source D** —
no duplication. Mapped against Overmind via direct source reads.

---

### E1 — Loop Charter Template (reusable skill)

> A structured charter with six mandatory sections that every loop must instantiate before
> running: GOAL (measurable "done") / WHERE THE WORK IS / HOW TO WORK / HOW TO CHECK
> YOURSELF (evidence, not confidence) / HOW TO REMEMBER (a LOOP-STATE.md read first,
> written last) / WHEN TO STOP (+ short report: done / blocked / needs-me).

**Overmind status: MISSING**

No per-run charter file exists. `data/loop_goal.json` (proposed in BB-2) covers only the
GOAL section. The HOW TO CHECK YOURSELF, HOW TO REMEMBER, and WHEN TO STOP sections have
no structured home.

**Alignment with existing Overmind concepts:**

| Charter section | Closest Overmind concept | Gap |
|----------------|--------------------------|-----|
| GOAL | `data/loop_goal.json` (proposed BB-2) | Partially covered if BB-2 is built |
| WHERE THE WORK IS | `nightly/selection.py:select_projects()` | Implicit in project list; not in a charter |
| HOW TO WORK | `nightly/runner.py` main loop | Behaviour only; no charter declaration |
| HOW TO CHECK YOURSELF | `llm_judge.py` + witnesses | Implemented; not declared per-run |
| HOW TO REMEMBER | `.progress_{date}.json` + `MemoryStore` | Machine-readable; not a LOOP-STATE.md |
| WHEN TO STOP | Hard timeout + project limit | No goal-based stop; no "done / blocked / needs-me" report |

**Implementation sketch (ADDITIVE, S effort):**
Add `overmind/activation/LOOP_CHARTER_TEMPLATE.md` as a versioned skill file:
```markdown
# Overmind Loop Charter — {date}
## GOAL
Measurable done condition: {e.g. "all high-risk projects CERTIFIED or circuit-open"}
## WHERE THE WORK IS
Projects: {select_projects result count}, path filter: {paths_filter}
## HOW TO WORK
Runner: nightly/runner.py --limit {N} --budget-usd {X} --max-retries 3
## HOW TO CHECK YOURSELF
Witnesses required: test_suite + smoke + (tier-3) numerical. Judge: QuorumJudge (cross-family).
Measurable bar: CERTIFIED verdict, not "tests pass".
## HOW TO REMEMBER
State file: data/LOOP-STATE_{date}.md (read at start, written after each project)
Crash-resume: data/.progress_{date}.json
## WHEN TO STOP
- Done: GoalChecker returns YES
- Blocked: circuit-open count > {threshold}; write NEEDS_ME_{date}.md; halt LLM phase
- Needs-me: items in NEEDS_ME_{date}.md await human action
```
Add `overmind charter init` CLI command that instantiates the template for a given run.
The charter is written to `data/charter_{date}.md` and read by `on_session_start.py`.

---

### E2 — "NEEDS ME" list

> Items requiring a human-only decision (spend money, delete, email a person) are parked on
> a NEEDS_ME list; the loop continues with the rest — never blocks the whole run, never
> self-authorizes.

**Overmind status: PARTIAL**

The risk checker (`nightly/runner.py:694-699`) skips high-risk projects with
`print(f"[SKIP] {proj.name}: {risk.reason}")` — the skip is silent. There is no structured
NEEDS_ME file that accumulates these for human review. The comprehension-debt gate (BB-1
proposed) blocks the loop, which is the opposite of the "never blocks the whole run" principle.

**Alignment with Sentinel prohibited-action classes:**
The Raytar article's NEEDS_ME list maps directly to Sentinel's explicit-permission gate:
actions that Sentinel marks BLOCK (delete, spend, push with bypass) must go to a NEEDS_ME
file, not silently skip and not block the run.

**Implementation sketch (ADDITIVE, S effort):**
In `nightly/runner.py:694-699` where `risk.skip` is logged silently, also append to
`data/NEEDS_ME_{date}.md`:
```markdown
# NEEDS ME — {date}
Actions below require explicit human authorization before the next nightly run can attempt them.
The loop continued past these items; no action was taken.

## Blocked by risk gate
- {proj.name} [{risk.reason}] — suggested action: {risk.suggested_action}

## Circuit-open (unfixable without human intervention)
- {proj.name} — {N} consecutive nights FAIL, class: {failure_class}
```
The nightly report already prints summaries — this adds a persistent, human-readable file.
The loop does NOT block; it appends and continues. `NEEDS_ME_{date}.md` is linked from the
morning dashboard.

Note: this is distinct from BB-1 (comprehension-debt gate), which *does* block promotion.
NEEDS_ME is non-blocking; the comprehension-debt gate is the blocking escalation for the
most serious cases (> THRESHOLD unresolved failures).

---

### E3 — Per-item retry cap (3 tries → blocked)

> Three tries per item, then log "blocked" and move on. A per-item circuit breaker,
> complementary to the global one (QW-1) which operates across nights.

**Overmind status: PARTIAL**

The global `LLMRepairer` cap is 5 calls per entire nightly run (`runner.py:724`: `for diag
in unfixed_diags[:5]`). This is a per-run cap, not a per-project cap. A single project can
consume all 5 slots. There is no 3-try per-project limit within a run.

**Relationship to QW-1 (circuit breaker):**

| Scope | Mechanism | Current Overmind |
|-------|-----------|-----------------|
| Per-item, within one night | 3 tries → log blocked, move on | PARTIAL (5 global slots, not per-project) |
| Per-item, across nights | N nights FAIL same class → circuit open | MISSING (QW-1 proposes this) |

**Implementation sketch (ADDITIVE, S effort):**
In `nightly/runner.py:716-742`, add `per_project_attempts: dict[str, int] = {}` before the
repair loop. Inside the loop, increment `per_project_attempts[diag.project_id]`; if count
reaches `MAX_RETRIES_PER_PROJECT` (default 3), append to `NEEDS_ME_{date}.md` and
`continue`. This is independent of the 5-call global LLM cap and complementary to QW-1.

---

### E4 — Self-check: second model copy confirming against the measurable bar after every turn

> A second copy of the model (separate instance) confirms against the measurable bar after
> every turn/project, not just at the end. This is the /goal pattern made per-item. Key
> distinction from article D: the bar is *measurable* (green tests, baseline within
> tolerance) — not the agent's own confidence that it's done.

**Overmind status: PARTIAL**

`LLMJudge` + `QuorumJudge` already implement the independent-verifier pattern per project
(`llm_judge.py`). The existing judge IS the self-check. What Raytar adds:

1. The check should be against the **measurable bar** (does CERTIFIED verdict exist AND
   does it satisfy the goal condition?), not just "did the judge return PASS?".
2. The self-check should happen after **every item/turn**, not just at the end of the batch.

Gap: The judge is called once per project; it judges whether the project passes, but it does
not check whether passing this project advances the overall loop goal. The GoalChecker
proposed in BB-2 would close this, but only runs at end of the full run, not per-project.

**Implementation sketch (ADDITIVE, S effort — incremental to BB-2):**
In `_run_verification()` after each project bundle is written, add a lightweight
`GoalChecker.check_project(proj, bundle, loop_goal)` call that returns:
- `ADVANCES_GOAL` — project contributes to the fixpoint (e.g. was CERTIFIED and is high-risk)
- `NEUTRAL` — does not advance or regress the goal
- `REGRESSES_GOAL` — was previously CERTIFIED and is now FAIL

Log the per-project goal-delta to `data/LOOP-STATE_{date}.md`. This does not change the
verdict; it is observability only (fully ADDITIVE). The end-of-run GoalChecker can then
consume these per-project signals for a faster convergence check.

---

### E5 — When NOT to loop: decision rule

> One-off tasks → plain prompt (cheaper); vague goals → define the measurable goal first;
> honest cost note: a self-checking loop runs the model several times per item → burns
> usage faster than a plain run.

**Overmind status: N/A (documentation)**

Raytar's decision rule, codified for Overmind context:

| Situation | Use | Rationale |
|-----------|-----|-----------|
| Single project, ad-hoc check | `overmind verify <path>` (plain) | One model call per witness; no loop overhead |
| Known project list, run once | `nightly/runner.py` (batch) | Current model; no re-entry needed |
| Goal-directed campaign ("get all tier-3 green") | `--loop-mode` (BB-2) | Re-entry loop justified; measurable fixpoint exists |
| Vague goal ("make things better") | **Do not loop yet** | Define measurable done condition first; write charter |
| Goal provably unachievable this run | Circuit open / NEEDS_ME | Stop LLM spend; surface to human |

**Honest cost note for Overmind:**
A nightly run with QuorumJudge (2 backends) + LLMRepairer (up to 5 calls) can consume
7-12 LLM calls per failing project. In `--loop-mode` with 3 iterations over 50 projects
that start failing, this is 1,000-1,800 calls. The budget ceiling (QW-2) is the primary
guard. Loop mode should only be enabled with an explicit `--budget-usd` flag set.

---

## Source F — "Vector RAG Isn't Enough — I Built a Context Graph Layer for Multi-Agent Memory" (Emmimal P Alexander, TDS, Jun 2026)

Full text not provided; key findings given verbatim by user. Repo: `github.com/Emmimal/context-graph-benchmark`.

### F.1 Benchmark results

Multi-agent memory benchmark: 3 architectures, 18 graded queries (6 direct / 7 distant / 5 join), zero LLM calls, deterministic:

| Architecture | Accuracy | Tokens/query | JOIN accuracy |
|-------------|---------|-------------|--------------|
| Context Graph (NetworkX→Neo4j, 2-hop traversal) | **88.9%** | **26.9** | **80%** |
| Raw history (full context dump) | 61.1% | 490.9 | 40% |
| Vector-only RAG (cosine similarity) | 50.0% | 75.9 | 20% |

**The decisive gap is JOIN queries** — combining two separately-stated facts (e.g. "project A uses module X" + "module X has a security issue" → "project A has a security issue"). Vector similarity retrieves each fact independently but structurally cannot combine them. Graph traversal collapses the two-hop path in one query.

### F.2 Two production bugs (directly relevant to Overmind)

**Bug 1 — STALE-FACT supersession:** On restating a `(subject, predicate)` triple with a new object, you must DROP the old edge or the graph returns stale facts with full confidence. The fix requires predicate-match detection at write time, not just on explicit call.

**Bug 2 — ENTITY-VOCABULARY mismatch:** "the auth module" ≠ node `AuthModule` without an alias/entity-linking step. In production this requires an LLM call at index time.

### F.3 Truthful assessment against Overmind's current memory layer

Verified by reading: `storage/models.py`, `memory/store.py`, `verification/claim_graph.py`, `storage/db.py`, `intelligence/portfolio_state.py`.

---

#### (a) Typed relationships enabling 2-hop / JOIN retrieval — MISSING

`MemoryRecord` (models.py:221) has two edge fields:
- `linked_memories: list[str]` — generic, untyped association by memory_id; no predicate label
- `derived_from: list[str]` — directed dependency edges (claim depends on evidence); no predicate label beyond the directionality

`ClaimGraph` (claim_graph.py) is a directed graph with only one edge semantics: "depends on". Its sole API is `retract()` — there is no retrieve-by-traversal or join-query path. It is never called during recall.

The retrieval path in `MemoryStore` is:
1. `search()` — SQLite FTS5 full-text search (`db.py:308-333`)
2. `semantic_search_memories()` — cosine similarity over stored embeddings (`db.py:335-367`)
3. `hybrid_search()` — FTS5 first; if < 3 results, augment with cosine; dedup (`store.py:94-118`)

None of these paths traverse graph edges. **Overmind's retrieval is architecturally vector + FTS, matching the "Vector-only RAG" baseline in the benchmark (50.0% accuracy on JOINs: 20%).**

A cross-project JOIN query — "project A is CERTIFIED; project A uses the cryptography module; what is the cryptography module's verdict?" — cannot be answered by the current retrieval layer. The two facts are stored as separate `MemoryRecord` rows with no typed relationship connecting them.

---

#### (b) Fact-supersession on restate — PARTIAL (explicit call only; no predicate-match detection)

`MemoryStore.supersede(old_id, new_memory)` (store.py:120-138) correctly implements supersession: sets `old.valid_until = now`, `old.status = "expired"`, links `new_memory.linked_memories` to the old id. The underlying semantics are correct.

**The gap vs. the article's Bug 1:** `supersede()` requires the caller to know `old_memory_id` explicitly. There is no automatic predicate-match lookup — nothing checks "does an active memory with the same (scope, predicate-equivalent-title) already exist before writing a new one?" The `extractor.py` / `dream_engine.py` pipeline that writes memories at session-stop does not call `supersede()` — it calls `save_batch()` which calls `upsert_memory()` directly (likely INSERT-or-UPDATE by `memory_id`, not by content-hash). So on restatement of a fact with a new value, an old conflicting memory can persist as `active` alongside the new one.

Verified: `store.py:29-31` (`save()`/`save_batch()` → `db.upsert_memory()`); the upsert key is `memory_id`, not a content-derived predicate hash.

---

#### (c) Entity-linking / alias resolution — PARTIAL, project-scoped only

`intelligence/portfolio_state.py:39-65` implements `project_identity_aliases()`: given a `ProjectRecord`, generates a frozenset of string aliases (slugify, lowercase, path normalization, id truncation). The `_project_identity_alias_map()` (line 137-143) builds a full alias→canonical_identity dict used to resolve scope mismatches when loading memories against bundles.

This is **project-entity linking only** — it normalizes "EvidenceOracle" → "evidenceoracle" → "evidence-oracle" → "evidence_oracle" so that a memory scoped to one form is found when looking up another. It is not a general entity-linking layer. For general memory entities ("the auth module", "the judge backend", "the scoring heuristic") there is no alias/entity-linking step.

---

### F.4 Recommendation: `memory_join_recall` eval + optional context-graph retrieval layer

**New eval first** (ADDITIVE, S effort): Before building any graph layer, add `evals/memory_join_recall.py` adapting the article's 18-query structure to Overmind's domain. Three query categories:

| Category | Example Overmind query | Expected source |
|---------|----------------------|----------------|
| Direct (6) | "What is the verdict for project X?" | Single memory lookup |
| Distant (7) | "What failure class occurred for project X two nights ago?" | Temporal scan over memories |
| JOIN (5) | "Project A and project B share a test runner. What is that runner's success_rate_7d?" | Two-hop: project→runner→attribute |

Benchmark all three current retrieval backends (FTS5, cosine, hybrid) against these 18 queries, deterministically, zero LLM calls. This gives a baseline before any graph layer is added. The eval harness pattern is already established in `evals/memory_recall.py` and `evals/memory_retraction.py`.

**Graph retrieval layer** (ADDITIVE, M effort, flag-gated): New `overmind/memory/graph_store.py`. Uses NetworkX (already likely available; if not, pure-Python dict implementation of 2-hop traversal is trivial). Builds a typed-relationship graph **on top of** the existing SQLite store — does not replace it. On `save()`, optionally indexes `(scope, predicate, object)` triples extracted from memory content. On `recall_join()`, executes 2-hop traversal. Gate: `OVERMIND_GRAPH_MEMORY=0` (default OFF). When ON, `hybrid_search` gains a post-step: if FTS5+cosine returns < threshold results for a query that looks like a join (two entity mentions), also run `graph_store.recall_join()` and merge.

**Supersession fix** (ADDITIVE, S effort): In `memory/extractor.py` or wherever facts are written at session-stop, add a `find_superseded(scope, title_hash)` pre-check before `save()`. If an active memory with the same normalized `(scope, title_key)` exists, call `supersede()` instead of `save()`. This closes Bug 1 without touching the retrieval path at all.

---

## No-Regression Framework

**Hard constraint:** No recommendation in this document may be adopted if it regresses the
current eval scores. This section defines how to apply that constraint.

### Baseline scores (from `evals/results/summary.json`, generated 2026-06-25)

Critical gauges — any adoption that moves these in the wrong direction is **blocked**:

| Eval | Metric | Baseline | Direction |
|------|--------|---------|-----------|
| `judge_masterkey` | `degenerate_false_pass_rate` | **0.0** | must stay 0.0 |
| `judge_masterkey` | `genuine_accuracy` | **1.0** | must stay 1.0 |
| `judge_masterkey` | `injection_boundary_false_pass_rate` | **0.0** | must stay 0.0 |
| `judge_masterkey` | `injection_signature_false_pass_rate` | **0.0** | must stay 0.0 |
| `quorum_decorrelation` | `overcount_rate_after` | **0.0** | must stay 0.0 |
| `quorum_decorrelation` | `honest_panels_unchanged_rate` | **1.0** | must stay 1.0 |
| `engine_routing` | `accuracy_routed` | **1.0** | must stay 1.0 |
| `engine_routing` | `routed_preserves_expensive` | **true** | must stay true |
| `memory_recall` | `recall` | **1.0** | must stay 1.0 |
| `memory_recall` | `stale_suppression_rate` | **1.0** | must stay 1.0 |
| `sandbox_policy` | `untrusted_unisolated_counts_as_pass_rate_after` | **0.0** | must stay 0.0 |
| `judge_cot_goldenset` | `no_regression` | **true** | must stay true |
| `verdict_tracing` | `tree_consistent` | **true** | must stay true |

Known weak score (not a regression target — this is a known gap):
- `specbench_style.heldout_pass_rate` = 0.3333 (specbench_gap = 0.3334; visible_only_false_certifications = 5)

### ADDITIVE vs INVASIVE classification

**ADDITIVE** — new module, new flag, or new file output; zero change to existing code
paths; existing evals are unaffected by definition. These can be implemented directly
on master after a pass of `python -m evals.run_all` to confirm no test infra side-effects.

**INVASIVE** — touches existing judge/quorum/verification/memory paths; could change the
behaviour of a path covered by an existing eval. These **must**:
1. Be developed on a branch (not master).
2. Have `python -m evals.run_all` run before the change and after, with scores recorded.
3. Be adopted only if every critical gauge above holds or improves.
4. Be gated behind a config flag (default OFF) until the branch eval scores are confirmed.

---

## Consolidated Findings Table

All items from Sources C, D, and E. ADDITIVE/INVASIVE classification and regression-safety
plan added.

| # | Source | What it is | Overmind mapping | Have? | Effort | ADDITIVE / INVASIVE | Regression-safety plan |
|---|--------|-----------|-----------------|-------|--------|---------------------|------------------------|
| 1 | Tower C3-1 | Circuit breaker (CLOSED/OPEN/HALF-OPEN, cross-night) | New `verification/loop_brakes.py`; gate before `AutoFixer` + `LLMRepairer` calls (`runner.py:400`, `:716`) | MISSING | S | **ADDITIVE** — new module + gate; does not touch judge/quorum/witness paths | Run `evals.run_all` before + after as sanity check; expect no change (no judge path touched) |
| 2 | Loop-D P5 | Budget ceiling (USD/phase) | New `--budget-usd` flag; running cost accumulator in `runner.py` LLM repair phase | MISSING | S | **ADDITIVE** — flag-gated; halts only when flag is set | Run `evals.run_all` before + after; expect no change |
| 3 | Loop-D P5 | Liveness heartbeat | 2 lines inside `_verify_with_timeout` poll loop (`runner.py:93-95`) | PARTIAL | S | **ADDITIVE** — writes a file; no logic change | Run `evals.run_all` before + after; expect no change |
| 4 | Loop-D P5 | AutoFixer blast radius | `OVERMIND_AUTOFIXER_WORKTREE=1` env flag; require worktree for auto-fix writes | PARTIAL | S | **ADDITIVE** — env-flag-gated, default OFF | Run `evals.run_all` before + after; expect no change |
| 5 | Tower C3-6 | Night-runner action allowlist | `SAFE_FIX_ACTIONS` frozenset gate in `runner.py:666`; `--unsafe-fixes` re-enables | PARTIAL | S | **ADDITIVE** — restricts fix scope; does not change verification logic | Run `evals.run_all` before + after; expect no change (fix phase not covered by current evals) |
| 6 | Loop-D P3 / E1 | STATUS.md + LOOP-STATE.md per iteration | New `write_status_md()` in `reporting.py`; `LOOP-STATE_{date}.md` written after each project | MISSING | S | **ADDITIVE** — new file output only | Run `evals.run_all` before + after; expect no change |
| 7 | Loop-D P7 | Manual-run gate before skill promotion | `manual_run_required=True` flag in `evolution/promotion.py` | PARTIAL | S | **ADDITIVE** — flag-gated, default OFF until validated | Run `evals.run_all` before + after; expect no change (evolution paths not in current evals) |
| 8 | E1 | Loop Charter Template | New `activation/LOOP_CHARTER_TEMPLATE.md` + `overmind charter init` CLI | MISSING | S | **ADDITIVE** — new files + CLI command only | No eval risk; documentation + new file |
| 9 | E2 | NEEDS ME list | Append to `data/NEEDS_ME_{date}.md` when `risk_checker.check()` skips; non-blocking | PARTIAL | S | **ADDITIVE** — better logging of existing skips; no logic change | Run `evals.run_all` before + after; expect no change |
| 10 | E3 | Per-item retry cap (3 tries → blocked) | `per_project_attempts` counter in `runner.py:716`; cap at 3; append to `NEEDS_ME` | PARTIAL | S | **ADDITIVE** — new per-project counter; complements global 5-call cap | Run `evals.run_all` before + after; expect no change |
| 11 | Loop-D P6 / E4 | Human comprehension-debt gate | Write `data/HOLD_FOR_HUMAN.md`; block `skill_library` + wiki updates until `--ack-hold` | MISSING | M | **ADDITIVE** — new blocking file check; does not alter verification path itself | Run `evals.run_all` before + after; expect no change (promotion paths not in current evals) |
| 12 | Loop-D P2 / E4 | Goal-directed stop condition + per-project self-check | New `activation/goal_checker.py`; `--loop-mode` flag; per-project goal-delta in `LOOP-STATE` | MISSING | M | **INVASIVE** — touches `on_session_stop.py` (memory extraction timing) | Branch required. Run `evals.run_all` before + after. Critical: `memory_recall.recall` (1.0) + `memory_retraction` must not regress. Gate behind `OVERMIND_LOOP_MODE=0` (default OFF). |
| 13 | Tower C3-3 | Hash-chained evidence ledger | Append `evidence_ledger.jsonl` in `reporting.py` after each bundle | PARTIAL | M | **ADDITIVE** — new append-only file; no existing path changed | Run `evals.run_all` before + after; expect no change |
| 14 | Loop-D P1 | Maker/judge cross-family enforcement | Assert `family_for_engine(maker) != family_for_engine(cheap_judge)` in `judge_factory.py:265-282` | PARTIAL | S | **INVASIVE** — touches `judge_factory.py`; could cause `judge_error` when only one model family is available | Branch required. Run `evals.run_all` before + after. Critical: `judge_masterkey.genuine_accuracy` (1.0) + `quorum_decorrelation.honest_panels_unchanged_rate` (1.0) must not regress. Gate behind `OVERMIND_MAKER_JUDGE_XFAMILY=0` (default OFF). |
| 15 | Tower C3-5 | Agent capability model + routing | Route by `quality_score / latency` per judge via `q_router.py` | PARTIAL | M | **INVASIVE** — changes judge selection logic in `judge_factory.py` | Branch required. Run `evals.run_all` before + after. Critical: `engine_routing.accuracy_routed` (1.0) must not regress. |
| 16 | Tower SPEC | Witness grading (A/B/C tiers) | Grade witnesses by credibility in `scope_lock.py` + `cert_bundle.py` | PARTIAL | M | **INVASIVE** — changes arbitration logic in `cert_bundle.py`; could alter CERTIFIED/REJECT verdicts | Branch required. Run full `evals.run_all`. Critical: `verdict_tracing.tree_consistent` (true) must hold. |
| 17 | Tower Orchestrator | Blackboard shared-state for quorum | QuorumJudge backends share findings before final vote | MISSING | L | **INVASIVE** — changes `llm_judge.py:QuorumJudge`; alters verdict path | Branch required. Critical: `judge_masterkey` suite must hold at 0.0/1.0. High risk — defer. |
| 18 | Tower SLO | Verification SLO monitoring | New `verification/slo.py`; metrics from nightly report | MISSING | L | **ADDITIVE** — new module reading existing outputs | Run `evals.run_all` before + after; expect no change |
| 19 | E5 | "When NOT to loop" decision rule | Documentation only; `--loop-mode` requires `--budget-usd` | N/A | S | **ADDITIVE** — documentation + CLI constraint | No eval risk |
| 20 | F (eval) | `memory_join_recall` — 18-query deterministic benchmark (direct/distant/join) | New `evals/memory_join_recall.py`; baselines FTS5 + cosine + hybrid on Overmind-domain queries | MISSING | S | **ADDITIVE** — new eval file; zero change to production paths | No eval regression risk; adds new measurement only |
| 21 | F (Bug 1) | Supersession on restate — predicate-match pre-check before `save()` | `memory/extractor.py` or session-stop writer: `find_superseded(scope, title_hash)` → call `supersede()` instead of `save()` | PARTIAL (explicit call only) | S | **ADDITIVE** — new pre-check before write; does not alter retrieval or retraction paths | Run `evals.run_all` before + after; critical: `memory_recall.recall = 1.0` must hold |
| 22 | F (core) | Context-graph retrieval layer (typed triples, 2-hop JOIN) | New `overmind/memory/graph_store.py`; augments `hybrid_search` post-step when `OVERMIND_GRAPH_MEMORY=1` | MISSING | M | **ADDITIVE** — new module + flag; default OFF; `hybrid_search` fallback unchanged when flag unset | Run `memory_join_recall` eval before + after enabling flag; also run `memory_recall` + `memory_retraction`; expect existing scores unchanged when flag OFF |

---

## Prioritised Adoption Shortlist

### Top 5 Quick Wins (effort S, ADDITIVE, safe for master)

All five are ADDITIVE. Run `python -m evals.run_all` before and after implementing each;
expect scores unchanged. Implement directly on master.

**QW-1 — Circuit breaker (cross-night) + per-item retry cap (QW-1 = items #1 + #10)**
Sources: Tower C3-1 (cross-night CLOSED/OPEN/HALF-OPEN) + Raytar E3 (per-item 3-try cap)
What: New `overmind/verification/loop_brakes.py`. Two classes:
  - `NightCircuitBreaker` — trips after 3 consecutive FAIL nights for same project+failure_class;
    persists to `data/circuit_states.json`.
  - `ItemRetryCounter` — tracks per-project attempts within one run; caps at 3; on cap,
    appends to `data/NEEDS_ME_{date}.md` and moves on.
Modules: wire `NightCircuitBreaker` into `runner.py:400` (pre-verify) and `runner.py:716`
(pre-fix). Wire `ItemRetryCounter` into the LLMRepairer loop at `runner.py:724`.
Regression safety: ADDITIVE. Does not touch judge/quorum/witness paths.

**QW-2 — USD budget ceiling + honest cost note (items #2 + #19)**
Sources: Tower `llm_tracker.py` + Raytar E5
What: `--budget-usd FLOAT` flag in `runner.py:parse_args()`. Running `run_cost_usd`
accumulator after each `upgrade_unknown` / `attempt_repair` call. Halt LLM phase (not whole
run) when ceiling hit. `--loop-mode` must require `--budget-usd` (CLI validation error
if loop mode attempted without budget).
Regression safety: ADDITIVE. Flag-gated; no effect when flag absent.

**QW-3 — Liveness heartbeat + NEEDS ME list + STATUS/LOOP-STATE files (items #3 + #6 + #9)**
Sources: Loop-D P5/P3 + Raytar E1/E2
What: Three new outputs written inside the existing nightly loop; zero logic change:
  1. `data/heartbeat_{project_id}.json` — every 60s in `_verify_with_timeout` poll loop.
  2. `data/NEEDS_ME_{date}.md` — appended when `risk_checker.check()` skips a project,
     when circuit opens, or when per-item retry cap is hit.
  3. `data/LOOP-STATE_{date}.md` — written after each project with Done/In-progress/Next/
     NEVER-touch + per-project goal-delta (ADVANCES_GOAL / NEUTRAL / REGRESSES_GOAL,
     evaluated purely against the DB — no LLM call needed for this part).
Regression safety: ADDITIVE (file outputs only).

**QW-4 — AutoFixer blast radius + action allowlist (items #4 + #5)**
Sources: Loop-D P5 + Tower C3-6
What: Two env-flag-gated guards in `runner.py:666`:
  1. `SAFE_FIX_ACTIONS = frozenset({"BASELINE_UPDATE", "FLOAT_PRECISION", "FORMULA_ERROR"})` —
     skip `attempt_fix` for other types during scheduled runs; `--unsafe-fixes` re-enables.
  2. `OVERMIND_AUTOFIXER_WORKTREE=1` env flag — require `WorktreeManager` for all auto-fix
     writes; skip if project has no `.git` dir.
Regression safety: ADDITIVE. Both flags default OFF; no change to existing scheduled runs
unless explicitly set.

**QW-5 — Loop Charter Template + manual-run gate (items #7 + #8)**
Sources: Raytar E1 + Loop-D P7
What:
  1. `overmind/activation/LOOP_CHARTER_TEMPLATE.md` — versioned skill file with 6 sections.
     `overmind charter init` CLI instantiates it to `data/charter_{date}.md`.
  2. `evolution/promotion.py` — `manual_run_required=True` flag (default OFF). When ON, a
     recipe requires `verified_in_manual_run=True` (set when `--manual` flag is present)
     before promotion to `SKILLS.json`.
Regression safety: ADDITIVE. Charter is a new file; promotion flag is additive opt-in.

---

**QW-6 — `memory_join_recall` eval + supersession pre-check (items #20 + #21)**
Sources: Alexander F benchmark + Bug 1 fix
What:
  1. New `evals/memory_join_recall.py` — 18 deterministic queries (6 direct / 7 distant / 5 join)
     adapted to Overmind domain (project→verdict, project→runner→attribute, runner→task→status).
     Zero LLM calls; scores FTS5, cosine, and hybrid against each category. Added to
     `evals/run_all.py` import list and `summary.json` output.
  2. `memory/extractor.py` (or wherever `save_batch()` is called at session-stop): add
     `_find_superseded(db, scope, title_key)` helper that runs
     `SELECT memory_id FROM memories WHERE scope=? AND status='active' AND title_key=?`
     before each write; if found, calls `store.supersede(old_id, new_memory)` instead of
     `save()`. `title_key = hashlib.sha256(normalize(title)).hexdigest()[:12]`.
Regression safety: eval addition is pure measurement. Supersession pre-check is ADDITIVE
(changes write path from upsert-always to supersede-if-exists); run `memory_recall` +
`memory_retraction` evals before + after; both must hold.

---

### Top 3 Bigger Bets (effort M, mixed ADDITIVE/INVASIVE)

**BB-1 — Human comprehension-debt gate (item #11) — ADDITIVE**
Sources: Loop-D P6 Death #4 + Tower `human_checkpoint.py` + Raytar E2
What: After the auto-fix phase in `runner.py`, if the same projects are FAIL/REJECT for ≥ 3
consecutive nights, write `data/HOLD_FOR_HUMAN.md`. Block `SkillLibrary.promote_recipe()`
and wiki compilation until `overmind check --ack-hold` is run. The run itself completes;
only the promotion/wiki phase is gated.
Distinction from NEEDS_ME: NEEDS_ME is non-blocking (written and loop continues). The
comprehension-debt gate is the escalation path for the most serious unresolved cases.
Regression safety: ADDITIVE. New blocking file check; does not touch verification, judge,
or quorum paths. Run `evals.run_all` before + after; expect no change.

**BB-2 — Goal-directed stop condition + self-check (item #12) — INVASIVE; branch + eval gate**
Sources: Loop-D P2 + Raytar E4
What: New `overmind/activation/goal_checker.py`. Reads `data/loop_goal.json`. After each
project, records goal-delta to `LOOP-STATE_{date}.md` (no LLM call — DB only). After the
full run, makes one cheap LLM call (Haiku via `SubprocessBackend`) returning yes/no+reason.
If no, injects the reason into `on_session_stop.py` memory extraction as context. `--loop-mode`
flag in `runner.py:main()` re-invokes the verification pass up to `max_iterations`.
Invasive because: changes `on_session_stop.py` code path (adds GoalChecker call before
DreamEngine); could affect memory extraction timing and what memories are created.
Regression-safety plan:
  1. Develop on branch `loop-engineering-goal-checker`.
  2. Run `python -m evals.run_all` on master → record scores (baseline above).
  3. Run `python -m evals.run_all` on branch.
  4. Critical gauges: `memory_recall.recall` must stay 1.0; `memory_retraction.transitive_recall_after`
     must stay 1.0; `judge_masterkey` suite must hold.
  5. Gate behind `OVERMIND_LOOP_MODE=0` (default OFF). Only activate after eval gate passed.
  6. Do NOT merge to master until eval gate confirmed.

**BB-3 — Hash-chained evidence ledger (item #13) — ADDITIVE**
Sources: Tower SPEC/`event_logger.py` + Loop-D P3
What: New `overmind/verification/evidence_ledger.py`. After each bundle write in
`reporting.py`, append `{id, ts, project_id, verdict, bundle_hash, prev_hash}` to
`data/evidence_ledger.jsonl`. SHA-256 the canonical event (excluding `prev_hash`) and chain.
Enables cross-run audit trail and SLO queries that the individual per-bundle signatures cannot.
Regression safety: ADDITIVE. New append-only file; no existing path changed. Run `evals.run_all`
before + after; expect no change.

---

**BB-4 — Context-graph retrieval layer (item #22) — ADDITIVE**
Sources: Alexander F (NetworkX graph, 2-hop traversal)
What: New `overmind/memory/graph_store.py`. In-memory NetworkX digraph with typed edges:
  `add_edge(subject_id, object_id, predicate="USES"|"VERIFIED_BY"|"FAILS_WITH"|"DEPENDS_ON")`.
  Populated on `save()` when `OVERMIND_GRAPH_MEMORY=1` by extracting typed triples from
  `MemoryRecord.content` via a regex/heuristic extractor (no LLM needed for structural facts
  like project→runner→verdict). Retrieval: `recall_join(entity_a, entity_b)` runs BFS up to
  2 hops and returns paths. Augments `hybrid_search` as a post-step when the query contains
  two distinct entity mentions and FTS5+cosine returns < 3 results.
  Persistence: on process exit, serialize graph to `data/memory_graph.json` (adjacency list).
  Load on init. Does NOT replace SQLite store — it is a supplementary index.
Prerequisite: `memory_join_recall` eval (QW-6 item #20) must be written first to provide
  the before/after measurement gate. Implement and measure baseline, then enable
  `OVERMIND_GRAPH_MEMORY=1`, re-run, report JOIN accuracy delta.
Regression safety: ADDITIVE, flag-gated (default OFF). When flag OFF, `hybrid_search`
  behavior is byte-for-byte identical to current. Run full `evals.run_all` + `memory_join_recall`
  before + after enabling the flag. Critical: `memory_recall.recall = 1.0` must hold;
  `memory_retraction.transitive_recall_after = 1.0` must hold.

---

### Invasive items deferred to branches (do not adopt on master without eval gate)

| Item | Risk | Critical eval to protect | Branch name suggestion |
|------|------|--------------------------|------------------------|
| #14 — Maker/judge cross-family enforcement | Could cause `judge_error` when Gemini key absent; mono-backend setups fail differently | `judge_masterkey.genuine_accuracy = 1.0`; `quorum_decorrelation.honest_panels_unchanged_rate = 1.0` | `loop-eng-xfamily-judge` |
| #15 — Agent capability model routing | Changes judge selection in `judge_factory.py` | `engine_routing.accuracy_routed = 1.0` | `loop-eng-judge-routing` |
| #16 — Witness grading (A/B/C tiers) | Changes `cert_bundle.py` arbitration; could alter CERTIFIED/REJECT verdicts | `verdict_tracing.tree_consistent = true` | `loop-eng-witness-grading` |
| #17 — Blackboard shared-state quorum | Major change to `llm_judge.py:QuorumJudge` | Entire `judge_masterkey` suite | Defer — high risk, low urgency |

---

## What to do next

**Order enforced by the no-regression constraint and Loop Engineering P7 ("prove manual
→ fold to skill → wrap in loop → schedule"):**

1. **Today — run baseline evals and record them:**
   ```
   python -m evals.run_all > evals/results/baseline_pre_loop_engineering.txt
   ```
   This is the reference snapshot for all future comparisons.

2. **This week — implement all ADDITIVE quick wins on master (QW-1 through QW-5):**
   After each QW, run `python -m evals.run_all` and confirm critical gauges unchanged.
   Commit order: QW-1 → QW-3 → QW-2 → QW-4 → QW-5 (brakes first).

3. **Next sprint — BB-1 (comprehension-debt gate) on master (ADDITIVE):**
   Then BB-3 (evidence ledger, also ADDITIVE). Both are safe for master.

4. **Branch work (after brakes are in and stable):**
   Open `loop-engineering-goal-checker` branch for BB-2. Run eval gate as described.
   Only merge when `memory_recall.recall = 1.0` confirmed on branch.

5. **Invasive items (#14-17):** Do NOT schedule until BB-2 is merged and the loop is
   demonstrably stable. The brakes must be in before the horsepower.

6. **Source F — memory layer (after QW-1 through QW-5 are stable):**
   Add QW-6 (`memory_join_recall` eval + supersession pre-check) as a low-risk
   measurement step. The eval alone is sufficient to quantify the JOIN gap before committing
   to BB-4. Implement BB-4 (context-graph layer) only after the eval baseline is in.

7. **Update this doc** when MRAgent (Source A) and external-research (Source B) agents
   return their results — those sections remain PENDING.
