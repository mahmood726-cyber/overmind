# Cutting-Edge Workflow Improvements — Multi-Agent Orchestration

**Date:** 2026-07-04
**Scope:** Research + design only. **No production system was changed.** This doc maps our
current orchestration stack to state-of-the-art techniques and proposes a *no-regression*
rollout that prioritizes the reliability failures we actually hit (wedge / auth / routing)
over novelty.

**Method:** Three read-only inventory agents read the real code (Overmind verification core,
the cluster harness, Sentinel, the Dispatch pattern, RapidMeta, and the design docs). External
research via web search/fetch of vendor engineering blogs, framework docs, and arXiv preprints.
Every external claim carries a URL. Where a paper's PDF would not yield a specific number, the
claim is stated qualitatively and flagged — no invented figures.

---

## 1. Current systems map + concrete weak points (evidence-based)

### 1.1 Overmind verification / orchestration core (`F:\overmind\overmind`)
Single-process, single-machine, sequential nightly verifier with a genuinely strong *verdict
logic* layer (UNVERIFIED vs CERTIFIED, degenerate/"master-key" output guards, cross-family
judge decorrelation, freshness/replay protection). The **plumbing** is where the fragility
lives.

| Weak point | Evidence | Failure it causes |
|---|---|---|
| Subprocess judges have a fixed 180s timeout, **no retry, no backoff** | `verification/judge_backends.py:48-70` | A hung `claude`/`codex` CLI wedges that judge for the full 180s; a quorum runs N backends serially → up to N·180s wall per verdict |
| **Headless auth silently degrades the quorum** | `CodexBackend.available()` needs `~/.codex`; FRONTIER-CLOSING §5 auth table: claude-in-subprocess errors without `ANTHROPIC_API_KEY`, both codex seats 401, only agy/Gemini live-respond | Advertised 3-family quorum is *configured* correctly but *runtime-blocked to 1 live engine* — no loud signal |
| **Hardcoded `C:/overmind/...` paths** in the ship path | `nightly/runner.py:736,934,952,973,1103,1309` | Breaks if run from `F:\` or a sandbox that can't reach the expected drive — this **is** the "sandbox can't reach F:" routing failure |
| Fail-**open** defaults scattered through the gates | `compound_judge.py:103-104` (empty steps → `passed=True`); `core/orchestrator.py:781` (judge FAIL only counts at confidence ≥0.7); `trajectory_scorer` `skip_verify` at ≥0.85 on hand-tuned constants; `resilience.PreFixRiskChecker` fails open on any git error (`:156-157,176-177`) | Low-confidence FAILs and degenerate states pass silently |
| Non-atomic / exception-swallowing state saves | `loop_brakes.py:143,153` (`_load/_save` swallow all exceptions → corrupt state silently resets breaker to CLOSED); `resilience.py:338-339` non-atomic `write_text` | A tripped circuit breaker can silently re-enable a project that should stay blocked |
| The **only real wedge defense** (multiprocessing tree-kill) lives in exactly one file | `nightly/runner.py:108-187` (psutil process-tree kill); base `verification/verifier.py` and the core orchestrator subprocess paths only do `communicate(timeout=5)` after kill | Stray grandchild processes survive on Windows outside the nightly path |
| Span tracing is built but **not threaded through** | `verification/verdict_trace.py` is OTel-shaped but most callers pass `tracer=None`; `meta_verification.run_meta_verification` is never called by the nightly runner (manual tool only) | We cannot see *why* a run failed; the canary that would catch a broken verifier never runs automatically |

### 1.2 Cluster harness (`F:\overmind\overmind\cluster`, branch `cluster-coordination-2026-06-25`, **unmerged, not in CI**)
Capability-aware, truth-gated SSH job dispatcher over Tailscale. Real (`SSHExecutor`/`SSHTransport`
replaced the old `NotImplementedError` stub). `JobScheduler` does capability+load routing with
requeue-on-offline. The "truth gate" (`assert_command_safe`, `transport.py:46`) refuses
force-push / `SENTINEL_BYPASS` / `--no-verify` before a command leaves the host.

| Weak point | Evidence | Failure it causes |
|---|---|---|
| **Single shared SSH key across all nodes, no revocation path** | `nodes.seed.json:12,27,42` all use `~/.ssh/node2_ed25519`; `onboard.py:70-74` only *appends* keys | One key compromise = whole fleet; a lost laptop can't be de-authorized |
| **Stale/absent key is misclassified as transient** → silent requeue | `transport.py:71-83` keys transient off ssh exit 255 / `permission denied (publickey`; `scheduler.py:200` requeues with **no backoff/jitter** | An auth failure loops as a "transient blip" instead of failing loudly — matches the headless-auth-revocation pain |
| Windows `ssh→cmd.exe` brittleness only half-handled | Health probe is single-line by necessity (`health.py:38-45`); dispatched **job** commands get *no* single-line/quoting guard | A multi-line or POSIX-shaped job command silently truncates/misparses on a Windows remote |
| No streaming / socket-buffer handling; sticky-offline within a run | Single blocking `subprocess.run(..., capture_output=True, timeout=…)` (`transport.py:122-131`); a node marked offline mid-batch is never re-probed (`scheduler.py:193`) | Large-stdout jobs can stall; a transient blip permanently removes a node for the whole batch |
| **SPOF: in-memory registry, no persistence** | `registry.py:113` `NodeState` in-memory only | A dispatcher crash loses all assignment/requeue state — no resume |
| Remote load unobservable on Windows | `health.py:42`, CLUSTER.md:12-14 (`None`) | Load-balancing degrades to in-flight-count only |

### 1.3 Sentinel (`F:\Sentinel`; `C:\Sentinel` mirror) — pre-push rule engine
57 rules, fail-closed on empty registry / crashed scan (push BLOCKED). Tamper-evident bypass
log with a sha256 hash chain. Solid gate design.

| Weak point | Evidence | Failure it causes |
|---|---|---|
| **No per-rule / per-file execution timeout — ReDoS wedges the pre-push hook** | Scan loop is a plain `for rule in reg.all_rules(): rule.check(ctx)` (`scan.py:188-194`); YAML rules `re.compile` rule-authored patterns and run them per line (`yaml_loader.py:121-123`); only bound is a 5 MB file cap | A catastrophic-backtrack pattern hangs the whole push with **no watchdog** — this is the ReDoS/session-wedge risk, inside our own gate |
| Inconsistent git file-discovery fallback | `git_files.py:176-179` fails closed (yields nothing) vs `yaml_loader.py:243-249` rglob fallback | A corrupt `.git` makes some rules silently scan zero files → WARN-level rules pass falsely |
| Plugin loader executes any `.py` dropped in `rules/plugins/` | `registry.py:32-36` | Arbitrary code at push time |
| Auto base-ref can pick the wrong base | `payload.py:90-96` | A multi-commit branch push may scan only the last commit's diff |

### 1.4 Dispatch pattern & RapidMeta
- **Three distinct "dispatch" concepts** — the legacy `cluster/dispatch.py` single-node thread-pool
  fan-out (only ever uses `local_nodes()[0]`, `dispatch.py:40-45`), the real `JobScheduler.schedule()`
  cross-machine routing, and `session_manager.dispatch()` (`core/orchestrator.py:170`) which is the
  actual production task→runner loop. Naming collision is itself a maintenance hazard.
- **RapidMeta** (`F:\rapidmeta-finerenone`): generator-driven "living meta-analysis" dashboards.
  Its `STUCK_FAILURES.md` (~2,900 lines) is dominated by **`P0-denominator-logic`** — hundreds of
  auto-generated apps with arithmetically impossible 2×2 cells (events > N, e.g. `CAPLACIZUMAB_TTP
  cE=524 > cN=39`). Only **17 of ~960 real dashboards are externally benchmark-validated**. This is
  an *extraction-quality* liability, and the relevant lesson for orchestration is **verification
  coverage that scales with generation** (see technique #9).

**Cross-cutting theme:** verdict *logic* is frontier-grade; the recurring failures are all in the
*execution substrate* — subprocess hangs with no watchdog/retry, auth that degrades silently,
in-memory state with no durable resume, and observability that is built but not turned on.

---

## 1.5 Loop-Engineering scorecard — where we meet the bar and where we fall short

**Source (practitioner):** the "Loop Engineering" pattern popularized by **Boris Cherny** (creator of
Claude Code, Anthropic) — *"I don't prompt Claude anymore. I write loops, and the loops do the work.
My job is to write loops"* — relayed and framed by practitioner write-ups (Cortex / @0xCortexl;
Addy Osmani; and the open-source `loop-engineering` skills). Verified summary:
https://noqta.tn/en/news/anthropic-loop-engineering-boris-cherny-autonomous-claude-code-2026 and the
community field guide https://lushbinary.com/blog/loop-engineering-ai-coding-agents-guide/ (see also
https://github.com/cobusgreyling/loop-engineering with its `loop-audit`/`loop-cost` tooling, and
https://github.com/selmakcby/loop-engineering "un-foolable verification gate" skill).

> **Truth-first on the numbers:** Cherny's quantified claims are **"~70% more shipped per head"** and
> a **"2–3× quality boost from verification,"** both attributed to a *Platformer* interview / internal
> Anthropic data with **no primary measurement or benchmark cited**. I found **no support for an "8×"
> figure** anywhere in the sources — do **not** repeat "8×" as fact. The **"loop is net-negative below
> ~50% acceptance"** rule and **"cost per accepted change"** metric are sensible practitioner
> heuristics (echoed by `loop-cost` tooling), **not** measured constants — treat them as design
> guidance, not evidence.

This is directly applicable because our stack *already* implements a partial version. Honest
scorecard against the article's three load-bearing requirements + five building blocks:

| Loop-Engineering requirement | Our current state | Verdict |
|---|---|---|
| **VERIFY = objective gate** (test/build/lint pass, *not* "a second agent agreeing") | **Mixed.** We *do* have real objective gates: the verifier's command allowlist + exit-code checks (`verifier.py`), `node --check` / build / test-suite witnesses, Playwright/browser runtime checks (`browser_checks.py`), byte/numeric-diff and numerical-continuity witnesses, RapidMeta's R-parity + benchmark-regression gate. **But** the *headline* verdict path often leans on **LLM judges / consensus-or-flag / cross-vendor witness** — exactly the "two optimists agreeing" the article warns about — and the LLM judge is **off by default** (`enable_llm_judge=False`), with a low-confidence FAIL silently accepted (`orchestrator.py:781`). | **PARTIAL — biggest gap.** Our consensus is only as strong as the objective witness *under* it. Where a task has a test/build/diff gate, we meet the bar; where the ship decision rests on judges agreeing, we do not. |
| **STATE file outside the conversation** | **Strong.** Atomic `.progress_<date>.json`, hash-skip cache, heartbeat files, `circuit_states.json`, `PROGRESS.md` convention, Sentinel/Overmind `STUCK_FAILURES.jsonl`. | **MEETS.** (Caveat: some saves are non-atomic / swallow exceptions — `loop_brakes.py:143,153`, `resilience.py:338-339` — see T4.) |
| **STOP condition (success + hard limit)** | **Partial.** Budget ceiling + `ItemRetryCounter` (3 fixes/project/run) + circuit breaker exist in the nightly loop. **But** subprocess judges/SSH have **no hard timeout ceiling with backoff** (T1), cluster requeue is unbounded-ish per node (T6), and there is no explicit **cost/token stop** tied to acceptance. | **PARTIAL.** Item/loop caps are real; per-subprocess and per-node hard stops are not (this is what T1/T6 add). |
| **Automation / heartbeat** (cron/schedule/goal-condition) | Nightly runner + scheduled SKILL.md tasks + heartbeat files. | **MEETS.** |
| **Skills (SKILL.md project knowledge)** | `SkillLibrary`/`SkillArchive` + scheduled skill tasks. | **MEETS.** |
| **Maker/checker sub-agents** (writer ≠ stronger adversarial reviewer) | `multi_persona.py` already enforces **reviewer ≠ writer runner**; family-decorrelation drops same-vendor judges. | **PARTIAL → strong once Codex is re-authed** (T11): Claude-maker + **Codex-checker** is the article's exact pattern, and Codex is our strongest bug-finder — but both Codex seats are 401-revoked today. |
| **Connectors (act, not suggest)** | Sentinel git-hook *acts* (blocks pushes); Overmind writes artifacts. No Linear/Slack/GitHub-issue write-back loop. | **PARTIAL.** We act on the repo; we don't yet close the loop into issue trackers. |
| **Cost per accepted change** (the metric that matters) | **Not tracked.** We measure verdicts and eval deltas, not tokens-per-accepted-fix or acceptance rate. | **MISSING.** This is a clean, low-risk observability add (folds into T3). |
| **Shared signal store** (loops write signals other loops read) | Partial/implicit: Sentinel `STUCK_FAILURES.jsonl` *is* read by Overmind as a witness. No general cross-loop signal bus linking RapidMeta / methods / clinic loops. | **PARTIAL.** The `STUCK_FAILURES.jsonl`→Overmind link is a working seed to generalize. |

**Failure modes the article names — which we've hit:** premature completion / "Ralph Wiggum" (our
fail-open low-confidence-FAIL-as-PASS and `compound_judge` empty-steps default are exactly this);
goal drift over long sessions (no standing AGENTS.md/goal reread per run is enforced in the loop);
comprehension debt (read every diff — the RapidMeta `P0-denominator-logic` at-scale bug is what
un-reviewed generated output looks like); token-cost compounding (untracked — see cost-per-accepted).

**Build-order discipline** (manual-reliable → Skill → loop w/ gate+stop → *then* schedule): a good
governance rule to adopt explicitly, and a direct check on the cluster branch being scheduled before
it is merged/CI-proven.

---

## 2. Ranked shortlist of adoptable techniques

Ranked reliability-first. Each carries: source (URL), what it is, mapping to our systems,
expected benefit, and regression risk + safe-adoption path.

### ★ HIGH-CONFIDENCE, LOW-RISK WINS

#### T1 — Universal subprocess watchdog: timeout + process-tree kill + bounded jittered retry
- **Source:** Anthropic, *How we built our multi-agent research system* — "letting the agent know
  when a tool is failing and letting it adapt works surprisingly well," combined with
  "deterministic safeguards"
  (https://www.anthropic.com/engineering/multi-agent-research-system). Reinforced by *When Tools
  Fail: Benchmarking Dynamic Replanning and Anomaly Recovery in LLM Agents* (ToolMaze), which
  frames execution-level robustness — detect/diagnose/recover from runtime tool failure — as the
  central unsolved problem (https://arxiv.org/abs/2606.05806), and *PALADIN: Self-Correcting
  Language Model Agents to Cure Tool-Failure Cases* (https://arxiv.org/abs/2509.25238).
- **What it is:** One shared helper that wraps every external-process call in (a) a hard wall-clock
  timeout, (b) a **process-tree** kill on expiry (not just `terminate()`), (c) a capped number of
  retries with exponential backoff + jitter, and (d) a structured `TOOL_TIMEOUT` / `TOOL_ERROR`
  result the caller can branch on. We **already have the proven pattern** — the psutil tree-kill in
  `nightly/runner.py:108-187` — it just needs to become the single code path.
- **Maps to:** `verification/judge_backends.py:48-70` (180s-no-retry judges), the cluster
  `transport.py:122-131` (blocking `subprocess.run`, no backoff), and Sentinel rule execution.
  Consolidate through the existing `overmind/subprocess_utils.py`.
- **Benefit:** Directly kills the #1 pain — hung/wedged subprocess sessions — across judges,
  witnesses, and SSH. Removes the N·180s serial-quorum worst case.
- **Risk / safe adoption:** Minimal; purely additive. Ship behind `OVERMIND_SUBPROC_WATCHDOG`
  defaulting to **shadow (log-only)**: record what *would* have been killed/retried for one nightly,
  confirm zero verdict deltas, then enforce. Rollback = flip the env flag.

#### T2 — Per-rule execution watchdog in Sentinel (ReDoS containment)
- **Source:** Our own proven tree-kill pattern (`nightly/runner.py:108-187`) applied to the gap;
  motivated by the reliability-science framing that per-step robustness dominates long-horizon
  outcomes (*Beyond pass@1: A Reliability Science Framework for Long-Horizon LLM Agents*,
  https://arxiv.org/abs/2603.29231).
- **What it is:** Run each `rule.check(ctx)` under a wall-clock cap in a killable worker; on
  timeout, emit a `RULE_TIMEOUT` WARN and continue rather than letting one catastrophic-backtrack
  pattern hang the entire pre-push hook.
- **Maps to:** `sentinel/.../scan.py:188-194`, `yaml_loader.py:121-123`.
- **Benefit:** Closes the ReDoS/session-wedge hole *inside our own gate* — the exact class the
  `regex_catastrophic_backtrack` rule warns about but can't protect itself from.
- **Risk / safe adoption:** Low. Fail-open to WARN (a slow rule never silently *blocks* a push);
  gate behind `SENTINEL_RULE_TIMEOUT_MS` (unset = current behavior). Shadow by logging per-rule
  durations across a week first to pick a threshold that never false-trips a legitimately slow rule.

#### T3 — Turn on the span tracing we already built + emit per-judge/tool/node metrics
- **Source:** OpenTelemetry *AI Agent Observability — Evolving Standards*
  (https://opentelemetry.io/blog/2025/ai-agent-observability/) and Anthropic's report that "full
  production tracing let us diagnose why agents failed and fix issues systematically." Practitioner
  rule of thumb: "instrument everything before you optimize anything; close the loop from production
  trace to regression dataset."
- **What it is:** Thread the existing `verdict_trace.py` tracer through the orchestrator/verifier/
  judge paths (today most callers pass `None`) and record latency, timeout count, retry count, judge
  agreement, and per-node dispatch outcomes using GenAI semantic conventions.
- **Maps to:** `verification/verdict_trace.py`, `core/orchestrator.py`, the cluster scheduler.
- **Benefit:** Fixes the benchmark's biggest stated gap — *nothing is measured*. It is the
  prerequisite that makes every other change here A/B-testable, and it is the cheapest.
- **Risk / safe adoption:** Very low; tracing is side-effect-free and no-ops when the tracer is
  absent. Additive only.

#### T12 — Loop-Engineering hardening (objective-gate audit · cost-per-accepted-change · hard stops · maker/checker · signal store)
- **Source:** Boris Cherny's "Loop Engineering" pattern (§1.5) — objective VERIFY gate, external STATE
  file, and a real STOP condition as the three load-bearing parts; verified summary
  https://noqta.tn/en/news/anthropic-loop-engineering-boris-cherny-autonomous-claude-code-2026;
  field guide https://lushbinary.com/blog/loop-engineering-ai-coding-agents-guide/; `loop-cost`
  tooling https://github.com/cobusgreyling/loop-engineering. (Numbers are interview-attributed, not
  measured — see the truth-first note in §1.5.)
- **What it is:** A cluster of small, mostly-additive hardening moves that pull our existing partial
  loop up to the article's bar. Each is independently shippable:
  - **(a) Objective-gate audit — the highest-value item.** For every task type that can currently
    ship on *judges agreeing alone*, require a named objective witness underneath (test / build /
    `node --check` / Playwright runtime / byte-or-numeric diff). Where no objective gate exists,
    mark the task **human-in-the-chair**, not loop-eligible. This is the article's core warning
    applied to `orchestrator.py:781` and `enable_llm_judge=False`.
  - **(b) Cost-per-accepted-change metric** (folds into T3): emit tokens-per-accepted-fix and
    acceptance-rate per loop; surface when a loop drops below the ~50% practitioner break-even so it
    can be paused. Pure measurement — zero behavior change.
  - **(c) Hard stop conditions**: an explicit success+ceiling stop on every loop, including a
    token/cost ceiling — the piece T1 (subprocess) and T6 (per-node) supply at the substrate level.
  - **(d) Maker/checker split = Claude-maker + Codex-checker** — this is T11; the article names the
    exact pattern ("a stronger model, told to be adversarial, trust tests over its own read").
  - **(e) Anti-goal-drift**: enforce a standing AGENTS.md/goal reread at the start of each loop run
    (cheap, additive) to counter long-session drift.
  - **(f) Shared signal store**: generalize the working `STUCK_FAILURES.jsonl`→Overmind link into a
    small append-only signal bus so the RapidMeta / methods / clinic loops can write signals others
    read (compounding), rather than each loop being blind to the others.
  - **(g) Build-order governance**: codify manual-reliable → Skill → loop(gate+stop) → *then*
    schedule; apply it as a gate on scheduling the still-unmerged cluster branch.
- **Maps to:** `core/orchestrator.py` (a,c), `verdict_trace`/T3 (b), `review/multi_persona.py` +
  T11 (d), the loop entrypoints / SKILL.md tasks (e,g), Sentinel↔Overmind JSONL (f).
- **Benefit:** Closes the single biggest conceptual gap (consensus without an objective floor), makes
  loop economics visible before they surprise the invoice, and turns our partial loop into a
  compounding multi-loop system.
- **Risk / safe adoption:** (a),(b),(e),(f),(g) are **low-risk, additive/observational** — adopt-first
  tier. (c) rides on T1/T6's shadow→enforce path. (d) is gated on the Codex re-auth prerequisite
  (T11). None changes a verdict silently; (a) can *tighten* ship criteria, so introduce it as a WARN
  ("would-fail-without-objective-gate") for one cycle before it blocks.

### ◐ PROMISING, NEEDS VALIDATION

#### T4 — Durable-execution journal for cluster dispatch (crash-resumable state)
- **Source:** Diagrid, *Checkpoints Are Not Durable Execution* — "if your process crashes, no one
  knows. There is no supervisor, no watchdog, no heartbeat" and "if two processes resume the same
  thread_id simultaneously, there is no built-in coordination"
  (https://www.diagrid.io/blog/checkpoints-are-not-durable-execution-why-langgraph-crewai-google-adk-and-others-fall-short-for-production-agent-workflows).
  DBOS, *Durable Execution for Crashproof AI Agents*
  (https://www.dbos.dev/blog/durable-execution-crashproof-ai-agents). Temporal+LangGraph pattern
  (https://appscale.blog/en/blog/durable-execution-llm-agents-temporal-langgraph-checkpointing-2026).
- **What it is:** Persist node assignments and the job queue to an append-only journal; on restart,
  replay to reconstruct in-flight state with idempotent dedup so a crashed dispatcher resumes
  instead of losing all routing state.
- **Maps to:** the SPOF at `cluster/registry.py:113` (in-memory `NodeState`).
- **Benefit:** Dispatcher crash no longer loses assignments/requeues; enables safe restart mid-batch.
- **Risk:** Medium — introduces replay/idempotency logic that can double-execute if dedup is wrong.
  **Adopt additively:** start with a *journal-only* jsonl (append every assignment/verdict, replay
  on restart to skip completed jobs) before considering a full durable-execution runtime. Validate
  on the cluster branch (already unmerged) with injected crashes. Do **not** rip out the working
  multiprocessing model to bolt on Temporal/DBOS — that's a future evaluation, not a first step.

#### T5 — Fail-fast auth preflight + capability attestation before quorum
- **Source:** Anthropic's "deterministic safeguards" around adaptive agents (same blog); our own
  `verification/preflight.py` fail-closed ingredient-check pattern.
- **What it is:** Before assembling a judge quorum or dispatching to a node, probe each backend/node
  for live auth (does `claude -p` actually respond? is the codex seat 401?) and refuse to *advertise*
  a family/node it can't use. Emit an explicit `AUTH_DEGRADED` signal instead of silently running a
  1-engine quorum or requeue-looping a dead key.
- **Maps to:** `judge_factory.py` family-decorrelation (which currently trusts `available()`), and
  the cluster transient-vs-permanent misclassification (`transport.py:71-83`).
- **Benefit:** Ends the two silent-degradation failures — 3-family quorum collapsing to 1 live
  engine, and a stale SSH key looping as "transient."
- **Risk:** Low-medium (a preflight that is itself flaky could over-reject). Shadow-mode: log the
  attestation verdict without acting for a week, confirm it matches reality, then enforce.

#### T6 — Per-node circuit breaker + backoff/jitter on requeue (reuse `loop_brakes`)
- **Source:** Anthropic guardrails-to-prevent-spiraling; standard resilience practice. We already
  have `NightCircuitBreaker` for projects (`loop_brakes.py`).
- **What it is:** Extend the existing project-level circuit breaker to *nodes*, and add
  exponential backoff + jitter to `scheduler.py:200`'s immediate requeue so a flapping node isn't
  retried back-to-back, and a node marked offline can be re-probed once its breaker half-opens.
- **Maps to:** `cluster/scheduler.py:180-213`.
- **Benefit:** Stops flapping-node retry storms and the sticky-offline-for-whole-batch problem.
- **Risk:** Low; reuses a battle-tested internal pattern. Validate on the cluster branch with a
  deliberately flapping node fixture.

#### T7 — Credibility-weighted / debate-based judge consensus
- **Source:** *An Adversary-Resistant Multi-Agent LLM System via Credibility Scoring*
  (https://arxiv.org/abs/2505.24239); *Multi-Agent Debate for LLM Judges with Adaptive Stability
  Detection* (https://arxiv.org/abs/2510.12697); survey *From Generation to Judgment: Opportunities
  and Challenges of LLM-as-a-Judge* (https://arxiv.org/abs/2411.16594), which catalogs
  self-preference and ambiguity bias in single judges.
- **What it is:** Replace flat threshold voting (`QuorumJudge`) with credibility-weighted votes
  (down-weight historically-wrong backends) and/or a bounded debate round with early-stop when the
  panel stabilizes.
- **Maps to:** `verification/llm_judge.py:576-645`.
- **Benefit:** Higher judge accuracy and adversarial robustness (our `injection_clean_boundary`
  false-PASS is still 100% on the probe).
- **Risk:** **Medium-high** — adds inference cost and could regress if credibility weights are
  mis-estimated on our small keyword-distinct fixtures. **Shadow only:** run the debate/credibility
  judge alongside the current quorum, log disagreement on the held-out evals, and require it to beat
  the current quorum on measured accuracy *before* it touches a ship verdict.

#### T8 — Failure taxonomy → regression dataset loop (AgentDebug pattern)
- **Source:** *Where LLM Agents Fail and How They Can Learn From Failures* (AgentDebug,
  https://arxiv.org/abs/2509.25370; code https://github.com/ulab-uiuc/AgentDebug). Observability
  practice: "close the loop from production trace to regression dataset."
- **What it is:** Systematically classify each production failure trajectory and auto-promote it
  into a regression fixture, so recurring failure modes become permanent eval coverage. We already
  have `verification/failure_taxonomy.py` and an evals harness — this aligns them.
- **Maps to:** `failure_taxonomy.py`, `intelligence/eval_harness.py`, RapidMeta's `P0-denominator-logic`
  class (which is exactly the kind of scaled failure that should become a standing regression check).
- **Benefit:** Verification coverage that grows with generation instead of lagging it (the RapidMeta
  17-of-960 gap).
- **Risk:** Low-medium (mostly additive process); the risk is fixture bloat. Cap promotion rate and
  dedup by failure class.

#### T9 — Explicit handoffs + guardrails as first-class primitives (OpenAI Agents SDK model)
- **Source:** OpenAI Agents SDK — handoffs, guardrails (input/output validation), tracing as the
  three built-in primitives (https://openai.github.io/openai-agents-python/multi_agent/;
  https://developers.openai.com/api/docs/guides/agents/orchestration). Educational precursor: OpenAI
  Swarm (https://github.com/openai/swarm).
- **What it is:** Model our task→runner transitions as *explicit, typed handoffs* carrying a bounded
  context object, with guardrails validating inputs/outputs at each boundary — rather than the
  current implicit session dispatch.
- **Maps to:** `session_manager.dispatch()` / `core/orchestrator.py`.
- **Benefit:** Cleaner context propagation, fewer "subagent misinterpreted the task" failures
  (Anthropic's documented delegation failure mode), and a natural place to attach guardrails.
- **Risk:** Medium (touches the core loop). Design-only for now; prototype on a non-critical runner
  path before the nightly loop.

#### T10 — Scheduler-theoretic DAG execution for Dispatch + the cluster (SGH model)
- **Source:** arXiv 2604.11378 — *From Agent Loops to Structured Graphs: A Scheduler-Theoretic
  Framework for LLM Agent Execution* (Hu Wei), abstract + HTML: https://arxiv.org/abs/2604.11378 /
  https://arxiv.org/html/2604.11378. **Honesty flag up front: this is a position paper with an
  explicitly stated "no production implementation or empirical results" caveat; its predicted gains
  (`G_graph`, `G_plan`, `G_replan`) are "logical consequences of the framework's assumptions," not
  measured.** We adopt its *concepts*, not a claimed result.
- **What it is:** It unifies "agent loop" and "graph engine" on one axis — an agent loop is "a
  single-ready-unit scheduler" (`|𝒰| ≤ 1`, next unit chosen by "opaque LLM inference"); a graph
  harness makes execution a static DAG with a **deterministic scheduler** (`|𝒰| ≥ 1`) over nodes
  (tool calls / sub-tasks) and dependency edges, with **join semantics** — `all_of` (constructive
  parallelism, wait for all branches) and `any_of` (competitive parallelism, first success wins).
  Two more commitments are directly useful to us: (a) a **three-level escalation recovery protocol**
  — Level 1 bounded Retry (transient) → Level 2 Local Patch (reasoning error) → Level 3 Replan —
  which the paper argues "prevents unbounded recovery loops"; and (b) **immutable, versioned plans**
  with planning/execution/recovery separated into three layers, so there is "no mutable execution
  history that complicates debugging." Its worked example turns an 11-sequential-turn agent loop
  into 6 scheduling rounds via parallel waves.
- **Maps to:** the three colliding "dispatch" concepts in §1.4. Concretely: (i) the cluster
  `JobScheduler` already does capability+load routing but has **no dependency model** — yet
  `cluster/delta_skip.py`'s `ContractImpactGraph` is already a repo-dependency graph we could lift
  into DAG edges, giving *dependency-aware routing* (run a repo's dependents only after it passes)
  instead of ad-hoc fan-out. (ii) The escalation protocol formalizes and bounds what T1/T6
  (watchdog retry, per-node breaker) do piecemeal — Level 1 = watchdog retry, Level 3 = replan, with
  an explicit ceiling that stops the requeue storms and unbounded loops we hit today. (iii) `any_of`
  competitive parallelism is exactly the shape of a **cross-vendor quorum race** (dispatch the same
  verification to Codex/agy/Claude, take the first sound verdict) — a natural fit for the harness.
  (iv) Immutable versioned plans are the design rationale under T4's durable journal, and a routing
  plan pinned to explicit node/data locality is what prevents the **sandbox-can't-reach-F: mis-route**
  — the plan declares data-locality as a hard edge constraint rather than discovering it at run time.
- **Benefit:** A single, debuggable, dependency-aware execution model replacing three ad-hoc dispatch
  paths; bounded recovery by construction; parallel waves where today we fan out or run sequentially.
- **Risk:** **Medium-high, and evidence-light.** It's an unvalidated position paper, and a wholesale
  DAG-scheduler rewrite of the orchestrator is a large, regression-prone change. **Safe adoption =
  concept-adoption, not framework-adoption:** (1) implement the *bounded escalation protocol* first
  (it's the lowest-risk, highest-value idea and dovetails with T1/T6); (2) promote
  `ContractImpactGraph` to explicit DAG edges in the cluster scheduler behind a flag, shadow-compared
  against current routing for identical verdicts; (3) treat full plan-immutability/versioning as a
  design north-star realized incrementally via T4's journal — do **not** rip out the working loop to
  chase the paper's theoretical parallelism gains.

#### T11 — Codex-as-bug-finder cross-vendor QA lane
- **Source:** Practitioner design guidance (Mahmood) grounded in observed Codex strength at
  bug-finding / code review; reinforced by the family-decorrelation principle already in our judge
  layer (`judge_factory.enforce_distinct_families`) and Anthropic's finding that independent
  subagents "act as intelligent filters" catching what a single pass misses
  (https://www.anthropic.com/engineering/multi-agent-research-system). This is the `any_of` /
  cross-vendor idea from T10 applied specifically to review.
- **What it is:** A standing verification stage in which **Codex seats run independent bug-hunt /
  code-review passes** — as an additive, cross-vendor QA lane distinct from the Claude/agy judges —
  over the methods repos, the RapidMeta engine (`~31 JS engines`, ~14k lines), and the site. Findings
  land as advisory WARN (`sentinel-findings`-style) first, not ship-blocking, so a false positive
  never blocks a push. Because it is a *different vendor's* review, it decorrelates from our
  Claude-heavy judge panel — the strongest argument for keeping it.
- **Maps to:** `verification/judge_factory.py` / `review/multi_persona.py` (which already enforces
  reviewer ≠ writer runner) as a new persona/lane; wired into the nightly `runner.py` verification
  phase and dispatchable per-node via the cluster harness. RapidMeta's `P0-denominator-logic` class
  is exactly the kind of at-scale extraction bug a dedicated bug-finder lane should catch early.
- **Benefit:** A decorrelated, high-signal bug-finding pass on the code most exposed to silent
  correctness failures — directly addresses the RapidMeta 17-of-960 validation gap and the fail-open
  defaults flagged in §1.1.
- **Risk:** Low *by design* (advisory-only, additive, cross-vendor) — **but hard-blocked on a
  prerequisite**: per FRONTIER-CLOSING §5 and our session notes, **both Codex seats are token-revoked
  (401 / timeout) and need an interactive re-login on pc1** — OAuth cannot be re-established from a
  headless subprocess. Until that re-auth happens, the lane cannot run at all. Once live, gate it
  behind T5's auth attestation so a silently-expired seat downgrades the lane to `AUTH_DEGRADED`
  rather than passing an empty review.

---

## 3. No-regression rollout plan

**Governing principle:** reliability (wedge / auth / routing failures we hit today) before novelty —
organized as **Loop Engineering**: the deliverable of each step is a *better loop* (objective gate +
external state + hard stop), not a better prompt. Every step is additive and flag-gated; every
enforcement step is preceded by a shadow phase with a measured zero-regression gate; every step has a
one-flag rollback. The article's build-order rule governs sequencing throughout:
**manual-reliable → Skill → loop(gate+stop) → then schedule** — nothing gets scheduled before it is
reliable by hand.

**Step 0 — Prerequisite hygiene (not cutting-edge, but blocks everything):**
Portable paths. Replace the hardcoded `C:/overmind/...` in `nightly/runner.py` with config-derived
paths so the nightly runs from `F:\` or a sandbox. This *is* the "sandbox can't reach F:" fix and
must land first because it gates any shadow run on non-`C:` hosts. Pure refactor, covered by
existing tests.

**Step 1 — Observability + loop economics on (T3, T12b).** Thread the existing tracer through the hot
paths and start emitting judge/tool/node metrics **plus cost-per-accepted-change and acceptance-rate
per loop**. Side-effect-free; this is what makes Steps 2–4 A/B-testable *and* tells us which loops are
below the ~50% break-even. *Gate:* dashboards show non-empty spans and a cost-per-accepted number for
one nightly. *Rollback:* tracer defaults to no-op.

**Step 1.5 — Objective-gate audit + anti-drift (T12a, T12e) — the loop-engineering centerpiece.**
Classify every loop-eligible task by whether a *named objective witness* (test / build / `node --check`
/ Playwright / byte-or-numeric diff) sits under its ship decision. Where one exists, keep it; where the
decision rests on **judges agreeing alone**, emit a `WOULD-SHIP-WITHOUT-OBJECTIVE-GATE` **WARN** for
one full cycle (advisory, non-blocking), then promote to a hard requirement or reclassify the task as
human-in-the-chair. In the same step, add the standing AGENTS.md/goal reread at loop start.
*A/B gate:* the WARN cycle quantifies how many ships currently rely on consensus-without-a-floor before
anything tightens. *Rollback:* the gate is WARN-only until explicitly promoted.

**Step 2 — Watchdogs in shadow, then enforce (T1, T2).** Land the shared subprocess watchdog and the
Sentinel per-rule timeout **in log-only mode**. Run one full nightly + one week of pushes. **A/B
gate:** the watchdog path must show **zero verdict deltas** vs the current path (only timeouts that
*would* have hung anyway differ). Then flip `OVERMIND_SUBPROC_WATCHDOG` / `SENTINEL_RULE_TIMEOUT_MS`
to enforce. *Rollback:* unset the env flag — old code path is untouched.

**Step 3 — Auth preflight + node breaker/backoff in shadow (T5, T6).** On the cluster branch,
log attestation verdicts and would-be backoffs without acting; validate against a deliberately
dead-key and flapping-node fixture. Enforce once the attestation matches reality with no false
rejects. *Rollback:* flag flip; requeue reverts to immediate.

**Step 3.5 — Re-auth Codex, then stand up the bug-finder lane (T11).** *Prerequisite (do this before
anything Codex-dependent, including any 3-family quorum):* on **pc1, interactively re-login both Codex
seats** (`codex` OAuth cannot be restored from a headless subprocess; both seats are currently
401/revoked). Then run the Codex bug-hunt / code-review lane over the methods repos, the RapidMeta
engine, and the site as an **advisory (WARN-only) verification stage** — findings recorded, never
ship-blocking — for a full cycle. Promote a finding class to blocking only after it proves itself
(e.g. the RapidMeta `P0-denominator-logic` family). *Rollback:* the lane is additive; disabling it
removes only advisory output.

**Step 4 — Durable dispatch journal + bounded escalation (T4, escalation half of T10).** Add
append-only assignment/verdict journaling with idempotent replay on the (still-unmerged) cluster
branch, and implement SGH's **three-level escalation protocol** (Retry → Local Patch → Replan) as the
formal ceiling over T1/T6's retry/breaker logic. Validate with injected mid-batch dispatcher crashes:
a resumed run must not double-execute a completed job, and recovery must terminate at the escalation
ceiling instead of looping. Only after this is green should the cluster branch be considered for
merge/CI.

**Step 4.5 — Shared signal store (T12f).** Generalize the working `STUCK_FAILURES.jsonl`→Overmind
witness link into a small append-only signal bus the RapidMeta / methods / clinic loops can write to
and read from, so loops compound instead of running blind to each other. Additive; start read-only
(consumers subscribe, no loop changes its behavior on another's signal until validated).

**Step 5 — Research track, gated on measurement (T7, T8, T9, DAG half of T10).** Credibility/debate
judge, failure→regression loop, explicit-handoff refactor, and the DAG-scheduler concepts from SGH
(promote `ContractImpactGraph` to explicit dependency edges; `any_of` cross-vendor verdict racing)
run **shadow-only against the held-out evals / against current routing** and must beat the current
quorum/loop on *measured* accuracy or produce identical verdicts before touching any ship path. These
are deliberately last: highest-upside, but the only ones that can regress correctness — and SGH in
particular is an unvalidated position paper, so it earns its way in by measurement, not by citation.

**What to A/B or shadow (summary):** T12a objective-gate WARN cycle; T1/T2 verdict-delta shadow; T5
attestation-match shadow; T6 flapping-node fixture; T4 injected-crash replay test; T7
accuracy-on-evals shadow.
**Universal rollback:** every change is behind an env flag with the prior code path left intact for
one full nightly cycle before the old path is removed.

---

## 4. Confidence split (explicit)

**High-confidence, low-risk — adopt first:**
- **T1** Universal subprocess watchdog (timeout + tree-kill + bounded jittered retry) — reuses our
  own proven pattern; fixes the #1 wedge pain across judges/witnesses/SSH.
- **T2** Sentinel per-rule ReDoS watchdog — closes the session-wedge hole inside our own gate.
- **T3** Turn on the span tracing we already built — cheapest, side-effect-free, unblocks measurement.
- **T12** Loop-Engineering hardening — the **centerpiece**. Low-risk/additive sub-parts (a objective-
  gate audit as WARN, b cost-per-accepted-change, e anti-drift reread, f shared signal store, g
  build-order governance) are adopt-first; (c) hard stops rides on T1/T6; (d) maker/checker is T11.
  Our stack already meets the STATE-file, heartbeat, and Skills requirements — the real gaps are the
  **objective-gate floor under consensus**, **cost tracking**, and **hard per-subprocess/per-node
  stops** (§1.5 scorecard).
- (**Step 0** portable paths — prerequisite, not novel, but required for the "sandbox can't reach F:"
  class.)

- **T11** Codex-as-bug-finder cross-vendor QA lane — *low-risk by design* (advisory-only, additive,
  decorrelated from our Claude-heavy judges), **but hard-blocked until both Codex seats are
  re-authenticated interactively on pc1.** Once live, high-value; belongs in the adopt-first tier the
  moment the re-auth prerequisite is met.

**Promising, needs validation before it touches a ship verdict:**
- **T4** durable dispatch journal (idempotency risk — journal-only first).
- **T5** auth-preflight/attestation (flaky-preflight over-reject risk — shadow first).
- **T6** per-node circuit breaker + backoff (low risk, but validate on a flapping fixture).
- **T7** credibility/debate judge (cost + could regress on small fixtures — shadow-only vs evals).
- **T8** failure-taxonomy → regression loop (fixture-bloat risk).
- **T9** explicit handoffs/guardrails (touches the core loop — design/prototype only).
- **T10** scheduler-theoretic DAG execution (SGH) — **concept-adoption only, evidence-light.** The
  *bounded escalation protocol* is a genuine low-risk win (fold into Step 4); the full DAG-scheduler
  rewrite is a large, unvalidated bet (Step 5, shadow-gated). It is a **position paper with no
  empirical results** — adopt its ideas, never cite its predicted gains as fact.

**Speculative / flagged:** A full durable-execution *runtime* (Temporal/DBOS) replacing the working
multiprocessing model is attractive on paper but is a large rip-and-replace; it is explicitly *not*
recommended as an early step — revisit only after T4's journal proves the durability need in
practice. A wholesale SGH DAG-scheduler rewrite sits in the same bucket. The exact recovery-rate
figures in the tool-failure papers (ToolMaze, AgentDebug) could not be extracted from their PDFs in
this session, so they are cited for their *qualitative* contributions only — do not quote a specific
recovery percentage without reading the full text.

---

## 5. Assessed and explicitly excluded from the workflow shortlist

**arXiv 2603.15031 — *Attention Residuals* (Kimi Team)** — https://arxiv.org/abs/2603.15031.
*Honest verdict: not applicable to our orchestration stack.* This is an **LLM pretraining-architecture
technique**: it replaces standard PreNorm residual connections (which "accumulate all layer outputs
with fixed unit weights") with **softmax attention over preceding layers' outputs** so each layer
selectively aggregates earlier representations with learned, input-dependent weights, plus a
**Block AttnRes** variant that attends over block-level representations to cut memory overhead as a
"drop-in replacement for standard residual connections." It was integrated into **Kimi Linear**
(48B total / 3B activated) to mitigate PreNorm dilution and even out gradient magnitudes across depth.
It has **zero bearing on Sentinel / Overmind / the harness / Dispatch** — it operates inside model
training internals, not agent orchestration, tool use, or inference-time workflows. The *only* way it
would matter to us is if we ever pretrained or heavily fine-tuned our own base model — which is not on
any roadmap here. It is included in this doc for completeness and deliberately kept **out** of the
ranked shortlist so we don't shoehorn a training-time idea into a workflow problem. Only the
scheduler-graph paper (2604.11378) is directly workflow-relevant.

---

## Sources
- Anthropic — *How we built our multi-agent research system*: https://www.anthropic.com/engineering/multi-agent-research-system
- Diagrid — *Checkpoints Are Not Durable Execution*: https://www.diagrid.io/blog/checkpoints-are-not-durable-execution-why-langgraph-crewai-google-adk-and-others-fall-short-for-production-agent-workflows
- DBOS — *Durable Execution for Crashproof AI Agents*: https://www.dbos.dev/blog/durable-execution-crashproof-ai-agents
- AppScale — *Durable Execution for LLM Agents: Temporal + LangGraph (2026)*: https://appscale.blog/en/blog/durable-execution-llm-agents-temporal-langgraph-checkpointing-2026
- OpenAI Agents SDK — *Agent orchestration (handoffs, guardrails, tracing)*: https://openai.github.io/openai-agents-python/multi_agent/ and https://developers.openai.com/api/docs/guides/agents/orchestration
- OpenAI Swarm (educational): https://github.com/openai/swarm
- OpenTelemetry — *AI Agent Observability, Evolving Standards*: https://opentelemetry.io/blog/2025/ai-agent-observability/
- arXiv 2411.16594 — *From Generation to Judgment: Opportunities and Challenges of LLM-as-a-Judge*: https://arxiv.org/abs/2411.16594
- arXiv 2505.24239 — *An Adversary-Resistant Multi-Agent LLM System via Credibility Scoring*: https://arxiv.org/abs/2505.24239
- arXiv 2510.12697 — *Multi-Agent Debate for LLM Judges with Adaptive Stability Detection*: https://arxiv.org/abs/2510.12697
- arXiv 2509.25370 — *Where LLM Agents Fail and How They Can Learn From Failures* (AgentDebug); code: https://github.com/ulab-uiuc/AgentDebug
- arXiv 2606.05806 — *When Tools Fail: Benchmarking Dynamic Replanning and Anomaly Recovery in LLM Agents* (ToolMaze)
- arXiv 2509.25238 — *PALADIN: Self-Correcting Language Model Agents to Cure Tool-Failure Cases*
- arXiv 2603.29231 — *Beyond pass@1: A Reliability Science Framework for Long-Horizon LLM Agents*
- arXiv 2604.11378 — *From Agent Loops to Structured Graphs: A Scheduler-Theoretic Framework for LLM Agent Execution* (Hu Wei; **position paper, no empirical results**): https://arxiv.org/abs/2604.11378 / https://arxiv.org/html/2604.11378
- arXiv 2603.15031 — *Attention Residuals* (Kimi Team; **pretraining-architecture technique, assessed and excluded — see §5**): https://arxiv.org/abs/2603.15031
- **Loop Engineering** — Boris Cherny (creator of Claude Code, Anthropic), *"I write loops"* pattern, relayed by practitioner write-ups (Cortex/@0xCortexl; Addy Osmani). Verified summary: https://noqta.tn/en/news/anthropic-loop-engineering-boris-cherny-autonomous-claude-code-2026 ; field guide: https://lushbinary.com/blog/loop-engineering-ai-coding-agents-guide/ ; tooling: https://github.com/cobusgreyling/loop-engineering , https://github.com/selmakcby/loop-engineering. **Note:** quantified claims ("~70% more per head", "2–3× verification quality boost") are interview-attributed with no primary measurement; **no "8×" figure is supported by any source** and the "~50% acceptance break-even" is a practitioner heuristic, not a measured constant.

*Internal evidence in §1 comes from a read-only inventory of the live code on 2026-07-04; file:line
references are to the working tree of `F:\overmind`, `F:\Sentinel`, and `F:\rapidmeta-finerenone`.*
