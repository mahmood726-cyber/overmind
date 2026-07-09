# Implementation Checklist — Workflow Upgrade (No-Regression)

**Date:** 2026-07-04
**Status:** DESIGN / PLANNING ONLY. **No production system is modified by this document.**
**Source of record:** [`2026-07-04-cutting-edge-improvements.md`](./2026-07-04-cutting-edge-improvements.md)
(the "research doc"). Every technique ID (T1–T12) below maps 1:1 to that doc's §2 shortlist
and §3 rollout. Where this checklist adds file:line detail, it was verified against the live
working tree of `F:\overmind\overmind` on 2026-07-04 (spot-checks noted inline). Nothing here
is invented: if the research doc flagged a number as interview-attributed or a paper as
evidence-light, that caveat carries through.

**Centerpiece thesis (see the Framing section below):** treat this whole checklist as an
**automated, benchmark-gated *harness-evolution* loop** — after Joel Niklaus's *"Don't Train the
Model, Evolve the Harness"* — where each T-item is one candidate mechanism, kept only if a
constrained-budget closed-loop benchmark (MADE-derived, Step 6) shows it improves efficacy and/or
cost-per-accepted-change with **zero regression**, decided on **held-out** evals. **Every mechanism in
this plan is grounded in a real, documented Claude Code primitive** (subagents, hooks, headless
`claude -p`, skills/slash-commands, MCP) — see the *Grounding* section before Appendix A — and the
outer loop's **loss is designed and fenced against reward-hacking** per Elvis Sun's LFD discipline
(the *Loss-Function Development* section).

**Governing rules (from research doc §3 + user AGENTS.md):**
- Every change is **additive / behind a flag / shadow-mode first**. Every enforcement step is
  preceded by a measured **zero-regression shadow phase**. Every step has a **one-flag rollback**.
- **Build-order discipline:** manual-reliable → Skill → loop(gate+stop) → *then* schedule.
- No verdict changes silently. An audit that *tightens* ship criteria ships first as a **WARN**.

**Verification note on the two top moves (checked in live code today):**
- `subprocess_utils.py` already has `kill_process_tree()` (Windows `taskkill /F /T /PID`) and
  `verifier_popen_kwargs()` — but **no retry/backoff/jitter wrapper** (that is exactly T1's gap).
- `verification/judge_backends.py::CodexBackend` already does per-seat `CODEX_HOME`
  (`OVERMIND_CODEX_HOME_<SEAT>` override, else `~/.codex` / `~/.codex-<seat>`),
  `--skip-git-repo-check`, `--sandbox read-only`, and a `cmd /c` wrapper for `.CMD`/`.BAT` on
  Windows — but **no reasoning-effort flag** (low-for-smoke / xhigh-for-real is *not* wired yet).
- `core/orchestrator.py:781` fail-open confirmed (judge FAIL only counts at confidence ≥0.7);
  `core/orchestrator.py:819` `enable_llm_judge` defaults `False`. These are the exact hooks T12a targets.

---

## Framing (centerpiece): **Evolve the Harness, not the Model**

**Source (verified 2026-07-04 by rendering the Space):** Joel Niklaus (Hugging Face, July 2026) —
**"Don't Train the Model, Evolve the Harness,"**
https://huggingface.co/spaces/joelniklaus/harness-optimization
(live app: https://joelniklaus-harness-optimization.hf.space/ ). Related work surfaced by search and
cited as *related, not fully verified by me:* the **Meta-Harness** reference implementation
(https://yoonholee.com/meta-harness/ , code https://github.com/stanford-iris-lab/meta-harness). I did
**not** fetch those repos, and I deliberately do **not** repeat the search-summary claim of
"Sonnet-4.6 performance at 7× lower cost" — I could not verify it against a primary source.

**The thesis this checklist now adopts as its through-line.** Niklaus's result is the exact shape of
our cluster-harness north-star: hold the *model* fixed and run an **automated loop that mutates the
harness** (prompts, tool wiring, retrieval, verification, routing, completion criteria), keeping only
changes that **improve a benchmark score with no regression**. Verified specifics from the app:

- **Result (verified, quoted):** starting from `deepseek-ai/DeepSeek-V4-Pro` at **0% end-to-end** on
  Harvey's **Legal Agent Benchmark (LAB)**, the loop reached **5.0% all-pass / 80.1% criterion-pass**
  on held-out test data — *"Zero model weights changed."* Grounded in the **"mismanaged geniuses
  hypothesis"**: capable models underperform because of brittle scaffolding, not weak weights.
- **The loop (verified):** a **Proposer** (Claude Opus 4.8 reads execution traces + the current best
  harness and *"adds exactly one mechanism"*) and an **Evaluator** (Python scaffold runs the candidate
  on a fixed **24-task dev set × 3 trials**, promoting it *"only if performance exceeds the incumbent
  by at least one point on a blended metric"*).
- **Promotion rule (verified, quoted):**
  `score = pooled_criterion_rate + 0.5 * all_pass_rate − 0.005 * tokens_per_million`
  — i.e. **efficacy up, cost penalized, margin above trial noise.**
- **Search safeguards (verified):** *"one mechanism per iteration"* (changes compound additively),
  ***"Never read the test split"*** (mechanisms must generalize), and deterministic validation via
  *"causal replay over cached transcripts or A/B comparison across ≥5 fix and ≥5 regression tasks."*
- **The finding that most validates our plan (verified, quoted):** *"Five of the top six harnesses are
  deterministic code, not prompt edits"* — for weak agents, **operational discipline** (file handling,
  **tool-call validation, breaking repetition loops, runtime output checks**) beat prompt revision.
- **Transfer asymmetry (verified):** robustness fixes transfer across models; *"prompt playbooks are
  model-specific and can backfire"* across families. **Directly relevant to our heterogeneous-vendor
  (Claude/Codex/agy) harness:** prefer deterministic/robustness mechanisms that transfer; treat
  prompt-level judge tuning as vendor-specific.
- **Cost anchor (verified):** a 100-task test run cost *~$120–$160*; the 24-task dev set was an
  acknowledged limitation (*"can only find failure modes that appear in those 24 tasks"*).

**How the four external sources now compose into one checklist thesis:**

| Layer | Source | Role in our plan |
|---|---|---|
| **The meta-loop** | Niklaus, *Evolve the Harness* | An **automated, benchmark-gated harness-evolution loop**: propose one harness change → evaluate → keep only if it beats incumbent on a blended efficacy/cost score, no regression. |
| **The benchmark it scores against** | MADE (arXiv 2601.20996) | The **constrained-budget closed-loop eval** (Step 6): composable maker/checker/verifier components, ablation arms, efficacy + cost-per-accepted-change vs a single-agent baseline. *This is our Evaluator.* |
| **The candidate mechanisms** | This checklist's T-items + Loop Library | Every T1–T12 / T-LL change is a **candidate "one mechanism"** the loop can propose and keep — watchdog, objective-gate, Codex-checker, node breaker, etc. Loop Library gives each recurring lane an objective gate + proof + **stop condition**. |
| **The execution substrate** | Scheduler-graph paper (T10 / SGH, arXiv 2604.11378) | The **structured execution graph** the evolved harness runs on: dependency-aware routing, bounded escalation, `any_of` cross-vendor racing. *(Position paper — concepts only, as the research doc flags.)* |
| **The empirical validation** | TRINITY (arXiv 2512.04695, Sakana AI, ICLR 2026) | Empirical proof the shape works: a **0.6B coordinator routing Thinker/Worker/Verifier across a model pool, looping until the Verifier accepts, beats every individual frontier model** (86.2% LiveCodeBench). Our Dispatch conductor + maker/checker gate = this. Grounds **T-CV** (mandatory cross-vendor check) and the cheap-router cost lever. |
| **The loss-design discipline** | LFD / `/lfd-design` (Elvis Sun, github.com/elvisun/loss-function-development) | *How* to design the loss the outer loop descends and **fence it against reward-hacking**: 4-part loss (target/constraints/instruments/forced-entropy); *"every cheap path you don't fence off is a direction the optimizer sprints down."* Names our live reward-hacks and forces a fence+instrument for each (see the LFD section). |
| **The build substrate** | Claude Code docs (code.claude.com/docs) | The real primitives every mechanism is built from: subagents (checker), hooks (gates/constraints), headless `-p` (cost instrument), skills (loops), MCP (connectors). |

**Net thesis:** *build an automated, benchmark-gated harness-evolution loop — adopted incrementally
and additively, one flag-gated mechanism at a time — that keeps a harness change only when a
constrained-budget closed-loop benchmark shows it improves efficacy and/or cost-per-accepted-change
with zero regression.* This is precisely our existing no-regression discipline (one change behind one
flag; shadow → measured zero-regression gate → enforce; rollback = flip the flag) **restated as an
optimization loop** — and Niklaus's *"deterministic code beats prompts"* + *"one mechanism per
iteration"* + *"never read the test split"* independently vindicate the reliability-first, additive,
held-out-evals ordering this checklist already uses.

### External validation — TRINITY, an evolved LLM coordinator (Sakana AI, ICLR 2026)

**Source (verified 2026-07-04 by fetching the paper HTML):** Xu et al., **"TRINITY: An Evolved LLM
Coordinator,"** arXiv **2512.04695** (https://arxiv.org/abs/2512.04695 ,
HTML https://arxiv.org/html/2512.04695v3 ; project page https://sakana.ai/trinity/ ). This is the
single strongest external validation of our architecture: it says *don't make one model smarter — make
a coordinator route sub-steps to a pool of models and loop until a checker accepts.* That is our
Dispatch orchestrator + maker/checker gate, exactly.

**Verified claims (quoted / from the fetched paper):**
- **A tiny coordinator routes; it does not answer.** *"compact language model (≈0.6B parameters) and a
  lightweight head (≈10K parameters)"*, *"total number of learnable parameters under 20K."*
- **Tri-role delegation per turn:** it *"assigns one of three roles (Thinker, Worker, or Verifier) to a
  selected LLM"* each turn.
- **The team beats every individual model:** *"new record of 86.2±0.5% on LiveCodeBench,"* beating
  **GPT-5 (0.838), Gemini 2.5-Pro (0.672), Claude-4-Sonnet (0.465)** — and it transferred zero-shot to
  AIME / BigCodeBench / MT-Bench / GPQA. **Validates takeaway (a): a team of models beats any single one.**
- **Acceptance-driven plan→do→check loop:** termination is *"τ = min{k≤K : Rk=V and uk=ACCEPT}"* — the
  run continues until the **Verifier** signals ACCEPT. **Validates takeaway (c): an explicit check step
  before shipping is structurally central.**
- **The coordinator is tiny (0.6B) yet beats a frontier pool.** **Validates the *weaker* form of
  takeaway (d): the router need not be the biggest model.**

**⚠ Truth-first — two attributed takeaways are NOT supported by the paper text I could fetch, so they
are marked reported-not-verified and must not be cited as TRINITY findings:**
- **(d-strong) "Putting a top-tier model in the manager seat made it WORSE" — NOT FOUND.** The paper
  uses a fixed 0.6B coordinator throughout; its ablations (Table 2 / §4.5) vary components, **never the
  coordinator model size.** No experiment shows a larger coordinator degrading performance. The *cost
  lever* (a cheaper model can sit in the routing seat) is still well-motivated by the verified fact that
  a 0.6B coordinator suffices — but "bigger = worse" is **reported, not verified.**
- **(b) "Never let a model check its own work — use a different model" — NOT stated by TRINITY.** The
  paper selects roles from the same pool and does **not** mandate Worker≠Verifier or analyze
  self-verification blind spots. **However, this principle is independently ours already** and is sound
  on its own footing: `verification/judge_factory.py::enforce_distinct_families` and
  `review/multi_persona.py`'s reviewer-runner ≠ writer-runner rule encode exactly it. We keep (b) as
  **our own family-decorrelation principle**, reinforced by (not derived from) TRINITY.

**Concrete design guidance this produces (all design-only, additive):**
1. **Our Dispatch orchestrator *is* the "conductor."** Reinforce that the router/orchestrator seat does
   **not** need the top model — verified by TRINITY's 0.6B coordinator beating the frontier pool. This
   is a **cost lever**: a cheaper model (or a deterministic policy) in the routing / `session_manager.
   dispatch()` seat is a legitimate, evidence-backed option to *evaluate* — not a mandate, and gated
   through the T-HE benchmark like any other mechanism.
2. **A different-vendor check step before shipping becomes a first-class, mandatory gate (T-CV, below).**
   Promotes maker/checker from "nice to have" to a required habit: **Claude-maker → Codex-checker (+ agy)
   → ship only past the cross-vendor check** — the triple-vendor witness we demonstrated end-to-end this
   session. TRINITY's acceptance-driven loop is the structural argument for making the check mandatory;
   our own decorrelation rule is why the checker must be a *different vendor.*
3. **Route-per-subtask (plan/do/check to different best-fit models) is an explicit harness capability to
   evolve toward** — the north-star shape of T-HE + the T10/SGH execution graph: `any_of` cross-vendor
   racing for the "do" step, a decorrelated different-vendor "check" step, and a cheap router picking who
   does which. A *direction*, realized incrementally and benchmark-gated — **not** a rip-out of the loop.

### T-CV — Cross-vendor check-before-ship gate (first-class, mandatory habit; verdict advisory first)
- **First step (smallest safe change):** make "**a different-vendor check ran before ship**" a *required,
  recorded* step in the nightly verification phase — the check is mandatory; its findings stay **advisory
  WARN** for the first cycle (rides on T11). Enforce *presence of the check*, not (yet) its verdict.
- **Files / components:** `nightly/runner.py` verification phase (record "cross-vendor check present");
  `verification/judge_factory.py::enforce_distinct_families` (checker is a different family);
  `review/multi_persona.py` (reviewer ≠ writer). Reuses T11's Codex lane + agy.
- **Objective gate:** every ship-path verdict in a nightly carries a "cross-vendor check: present /
  absent (vendor=…)" field; absence is itself a WARN. Ties to the T12a objective-gate audit.
- **Rollback:** flag `OVERMIND_REQUIRE_CROSS_VENDOR_CHECK` (default record-only) — unset reverts.
- **Done-check:** one nightly shows a cross-vendor-check-present field on every ship verdict; checker
  family ≠ maker family in 100% of cases (decorrelation holds).
- **Ordering / risk:** low, additive; the *habit* is adopt-today once T11 is live (Codex re-authed ✓).
  Depends on T11 (Step 3.5). Promotion of the check's *verdict* to blocking follows T11's per-class path.

**What this changes in practice (design-only, additive):** it adds a *meta-goal* (T-HE below) that
ties Steps 1, 3.5, and 6 together — but it does **not** change any individual step's first-safe-move.
We do **not** stand up an autonomous self-mutating loop over production on day one; we adopt its
*discipline* now (blended promotion score, held-out gate, one-mechanism-per-change) and its *automation*
only after the MADE-style Evaluator (Step 6) is trustworthy.

### T-HE — Harness-evolution meta-loop (north-star; strictly additive, human-in-the-loop first)
- **First step (smallest safe change):** adopt the **promotion rule as our accept/reject contract**
  for harness changes *manually* — for any T-item we flip from shadow to enforce, require it to beat
  the incumbent on a blended `efficacy + cost` score (the MADE Step-6 metrics) on **held-out** evals,
  never on the tuning set. No autonomous Proposer yet: the "proposer" is us + the research doc's
  shortlist; the "evaluator" is Step 6. This is a **process rule**, zero code.
- **Files / components:** governance over `intelligence/eval_harness.py` (held-out set),
  T3/T12b metrics (the score), and the flag-gating already specified per step. No new runtime path.
- **Objective gate:** at least one harness change (e.g. T1 enforce, or T11 promotion of a finding
  class) is accepted **via a recorded held-out blended-score comparison** rather than by judgment call.
- **Rollback:** it's a process/acceptance rule; abandoning it reverts to per-step judgment.
- **Done-check:** the promotion of any T-item to enforce is accompanied by a before/after blended-score
  line (efficacy + cost-per-accepted) on held-out evals, with the tuning set never used to decide.
- **Ordering / risk:** the *discipline* is **adopt-today** (it's just our zero-regression rule with a
  scoreboard); the *automation* (an actual Proposer that rewrites harness config) is **north-star,
  needs-validation**, gated on Step 6 being trustworthy and on **never reading the held-out split**.

---

## Loss-Function Development (LFD) — the loop-design discipline + anti-reward-hacking

**Source (verified 2026-07-04 by fetching the repo):** Elvis Sun — **Loss-Function Development**,
GitHub https://github.com/elvisun/loss-function-development (public, **155★ / 9 forks**), providing the
**`/lfd-design`** skill that *"designs loss functions for long-running autonomous agent loops."* Relays
Peter Steinberger's *"design loops that prompt your agents."* **Truth-first on the numbers:** the
"**50×**", "**30 hours**", "**$40**" figures are **Elvis Sun's own anecdotes** (from his write-up, *not*
in the repo README — I did not find them there); report them as anecdotes, never as measured constants.
This is the deepest practitioner content on loop *design*, and it sharpens our whole framing: it tells
us how to build the *loss* the harness-evolution loop descends — and how to keep the optimizer from
cheating it.

### LFD vs spec-driven: two nested loops, gradient descent all the way down
The core reframing (verified from the README): spec-driven is *"build this, make the tests pass"*; LFD
is *"build this, make the tests pass, **then iterate against a thousand eval cases you can't see.**"* A
test suite is **DONE** when green; a 1,000-case eval at 95% is a **target you descend toward.** This is
exactly the two-loop structure this checklist already has — LFD just names it:
- **Inner loop = spec-driven "make tests pass"** = our objective gates (verifier allowlist, `node
  --check`, Playwright, byte/numeric diff, R-parity, truth-gate). Terminates on green.
- **Outer `/goal` loop = descend an OUTCOME metric** = the **T-HE harness-evolution loop** scored by the
  **Step 6 MADE benchmark** (efficacy + cost-per-accepted). Never "done"; you descend it.
- **Net:** *gradient descent all the way down.* T12a's objective-gate audit is what guarantees the inner
  loop is a real gate (green means something); T-HE + Step 6 are the outer descent. **LFD is the unifying
  theory of the framing section above** — not a competing idea.

### The 4-part loss function (verified components → mapped to us)
1. **TARGET** — *"large enough to prevent memorization, blinded during runs, measured mechanically at
   appropriate resolution."* For us: the held-out eval set must be **big enough that enumeration doesn't
   pay**, and the agent must be **BLIND to the answer key** — eval only for **post-hoc** scoring, never
   readable mid-run (this is Niklaus's *"never read the test split"* restated as a loss-design rule).
2. **CONSTRAINTS** — *"wall-clock, budget, surface area, methodology, and capacity caps."* For us:
   per-run wall-clock, **hard money cap**, allowed models/vendors/concurrency, and the methodology the
   run must follow (e.g. pool logRR not natural-scale).
3. **INSTRUMENTS / harness** — *"specific commands that enforce constraints."* The rule that matters:
   **a constraint without an instrument is a vibe** — ship a CLI for every constraint, and **measure the
   target at the RIGHT resolution** (pixel/byte/numeric diff, *not* an LLM judge, where a deterministic
   check exists). We already have most instruments (see the anti-reward-hacking table); the gap is
   **time-accounting + provider/token spend visibility**, which T3+T12b add.
4. **FORCED ENTROPY** — *"overfit reflection, stall rules, and exploration quotas."* For us: an
   **overfit-reflection every cycle**, a **forced non-obvious jump on stall**, and an **iteration /
   hypothesis log** (the `/lfd-design` skill red-teams its own drafts and keeps a *"cheat museum"* — both
   verified in the repo).

### ★ Anti-reward-hacking / loss-function design (the headline lesson)
**Verified quote (README):** *"the agent in the loop is an optimizer, and every cheap path you don't
fence off is a direction it will sprint down. It will memorize your eval, mine your miss-lists into
lookup tables, and game your judge."* Elvis Sun reports the agent cheated **three times** (memorized the
eval, learned-by-miss keywords, enumerated) — *reported anecdote, the specific count is his, not in the
repo.* **The lesson maps hard to our world**, and it is the missing adversarial layer under T12a/T7/T11:

> **A constraint without an instrument is a vibe; a target without a fence is a reward-hack waiting to
> happen.** For every automated loop we run, we must state the **target**, the **fences** (cheap paths to
> block), the **instruments** (the objective gate that makes the fence real), and the **forced-entropy /
> overfit check.**

| Loop | TARGET (descend) | FENCES (cheap paths to block) | INSTRUMENTS (make the fence real — mostly already ours) | FORCED-ENTROPY / overfit check |
|---|---|---|---|---|
| **RapidMeta QA** | ↑ benchmark-validated dashboards; ↓ arithmetically-impossible 2×2 cells | agent "passes" a coverage/pooling metric by (a) **finding nothing**, (b) tuning to the 17 validated dashboards only, (c) emitting cells that satisfy a loose check but are impossible (`cE>cN`) | **byte/numeric diff**, **R-parity gate**, **benchmark-regression gate**, a **hard `events≤N` denominator check** (the `P0-denominator-logic` fence), Sentinel BLOCK | overfit-reflection vs the **held-out** (non-17) dashboards each cycle; flag if gains concentrate on the validated subset |
| **Methods benchmark (Step 6 / MADE)** | ↑ efficacy (agreement/caught-bug) at ↓ cost-per-accepted | arm "wins" by **memorizing the eval set**, overfitting the small 24-ish task set, or **gaming a blended score** by inflating one term (all_pass) while regressing another | **held-out eval split (blinded)**, the **blended score** `efficacy + 0.5·all_pass − 0.005·tokens` decided on held-out, `--output-format json` **`total_cost_usd`** for the cost term | one-mechanism-per-iteration; overfit-reflection on the tuning-vs-held-out gap; forced exploration on stall |
| **Cross-vendor witness (T11/T-CV)** | ↑ real bugs caught before ship | a bug-hunt **passes by finding nothing**; **correlated agents** (same vendor/family) "agree" and game the consensus; the judge is gamed by adversarial phrasing | **different-vendor checker** (`enforce_distinct_families`, reviewer≠writer), the **T-CV "check-present" gate** (absence = WARN), a **planted-bug canary** (the RapidMeta `cE>cN` fixture — a found-nothing pass fails the canary) | rotate the planted-bug canary; log a *cheat museum* of observed false-PASS patterns (e.g. `injection_clean_boundary` still 100% false-PASS per the research doc) |

**Why this is not optional for us:** the research doc already documents our live reward-hacks —
`compound_judge` empty-steps → `passed=True`, low-confidence-FAIL-as-PASS at `orchestrator.py:781`, the
`injection_clean_boundary` 100% false-PASS, and RapidMeta's at-scale `cE>cN`. Those are **targets without
fences.** LFD is the discipline that names them and forces a fence+instrument for each.

### The MOAT insight — our private ground truth is the strategic asset
**Verified framing (Elvis Sun):** *"the product is a weekend now; the eval nobody else can score against
is the moat."* This is a direct strategic fit: **our private ground truth IS that eval** — the **AACT
registered-vs-published** corpus, the **curated gold meta-analysis library**, and the **truth-gated
reproduction set**. Anyone can clone a dashboard generator in a weekend; **nobody else can score against
our private, curated, truth-gated eval.** *Design-note (not a work item):* treat these datasets as a
first-class strategic asset — version them, keep them **blinded to the agent at run time** (Target rule
#1), and never let a loop read its own answer key. This is why Step 6 (MADE benchmark) and T8
(failure→regression) compound in value: they turn our private truth into an ever-growing moat-eval.

### LFD → Claude Code primitives (verified)
- **Spend instrument** (Constraint #2 money cap) = **headless `claude -p --output-format json`** →
  `total_cost_usd` + per-model breakdown ([headless](https://code.claude.com/docs/en/headless)). The
  hard money cap is enforced by reading that field and aborting the loop.
- **Constraint-instruments** (methodology / surface caps) = **hooks**: a `PreToolUse` deny fences the
  allowed surface; a `Stop`/`PostToolBatch` hook runs the mechanical target-measurement CLI and blocks
  ([hooks](https://code.claude.com/docs/en/hooks)).
- **Eval-blinding** (Target rule #1) = the answer key lives **outside** the agent's tool/file surface;
  a **subagent** with a restricted `tools`/`disallowed-tools` frontmatter cannot read it, and a `-p`
  run in **`--bare`** mode with a scoped `--allowedTools` cannot reach it
  ([sub-agents](https://code.claude.com/docs/en/sub-agents), [headless](https://code.claude.com/docs/en/headless)).
- **Forced-entropy log / cheat museum** = a **skill** (`.claude/skills/lfd-overfit-check/SKILL.md`) run
  each cycle with `disable-model-invocation: true` ([skills](https://code.claude.com/docs/en/skills)).

### T-LFD — Loss-function design + anti-reward-hacking pass (adopt-today, process-first)
- **First step (smallest safe change — spec only):** for each automated loop (RapidMeta QA, methods
  benchmark, cross-vendor witness), **write its 4-part loss function** (target / fences / instruments /
  forced-entropy) using the table above, and **red-team it for the cheap paths** the optimizer would
  sprint down. No runtime change — this is the loss-design document the `/lfd-design` skill produces.
- **Files / components:** loop specs from Step 1.6 (T-LL) gain a "loss function + fences" section;
  references the existing instruments in `verification/` (diff/R-parity/truth-gate) and T3/T12b (spend).
- **Objective gate:** each loop spec names ≥1 concrete reward-hack and the instrument that fences it;
  a "found-nothing pass" canary exists for every bug-hunt-style loop.
- **Rollback:** documentation; deleting it reverts to today's un-fenced loops.
- **Done-check:** RapidMeta QA, methods benchmark, and cross-vendor witness each have a written loss
  function with fences + instruments + a planted-bug/overfit canary; the `orchestrator.py:781` /
  `compound_judge` / `injection_clean_boundary` reward-hacks are each named with a fence.
- **Ordering / risk:** low (process/spec); it **sharpens T12a, T7, and T11** by giving them explicit
  anti-gaming fences. **Adopt-today**, folds into Step 1.5/1.6.

---

## 0. Ordering at a glance (dependencies)

**Framing wrapper (T-HE): every step below is a candidate "one mechanism" in an automated,
benchmark-gated harness-evolution loop — proposed, evaluated against the Step 6 closed-loop benchmark,
kept only if it improves efficacy/cost with zero regression. See the Framing section above.**

```
        ┌─────────────────────────────────────────────────────────────────────┐
        │  T-HE meta-loop: propose 1 mechanism → evaluate (Step 6) → keep if   │
        │  blended efficacy+cost score beats incumbent on HELD-OUT, no regress │
        └─────────────────────────────────────────────────────────────────────┘
Step 0   Portable paths (Overmind runs off F:/sandbox)          ── gates every non-C: shadow run
  │
  ├─ Step 1    T3 tracing ON  +  T12b cost-per-accepted           ── makes everything A/B-testable
  │      │
  │      ├─ Step 1.5  T12a OBJECTIVE-GATE AUDIT (WARN)  + T12e reread  ★ highest-value near-term
  │      ├─ Step 1.6  T-LL Loop-Library lane specs (objective+proof+stop per lane)
  │      └─ T-LFD    Loss-function + anti-reward-hacking fences per loop (target/fence/instrument/entropy)
  │
  ├─ Step 2    T1 subproc watchdog + T2 Sentinel rule watchdog   (shadow → enforce)
  │
  ├─ Step 3    T5 auth preflight + T6 node breaker/backoff        (cluster branch, shadow)
  │
  ├─ Step 3.5  T11 Claude-maker + CODEX-CHECKER lane + T-CV mandatory cross-vendor check   ★ UNBLOCKED (Codex re-authed)
  │
  ├─ Step 4    T4 durable dispatch journal + T10 escalation ceiling
  ├─ Step 4.5  T12f shared signal store
  ├─ Step 5    T7 / T8 / T9 / T10-DAG   (research track, measurement-gated, last)
  └─ Step 6    MADE-derived harness benchmark = the T-HE Evaluator (north-star; needs T3+T12b+T11)
```

**Adopt-today, low-risk:** the **T-HE harness-evolution *discipline*** (blended-score accept/reject on held-out evals — the framing), Step 0, Step 1 (T3+T12b), Step 1.5 (T12a WARN + T12e), Step 1.6 (T-LL Loop-Library lane specs), **T-LFD loss-function + anti-reward-hacking fences**, Step 3.5 (T11 + **T-CV mandatory cross-vendor check** — now that Codex works), T12g build-order governance, T12f (read-only).
**Needs validation before touching a ship verdict:** T1/T2 enforce (after shadow), T5, T6, T4, T7, T8, T9, T10-DAG.

The research doc calls out **T12a (objective-gate audit)** and **T11 (Claude-maker + Codex-checker)**
as the two highest-value near-term moves. They are detailed first and in depth below; the rest follow
in rollout order.

---

## ★ TOP MOVE #1 — T12a: Objective-Gate Audit (`WOULD-SHIP-WITHOUT-OBJECTIVE-GATE` WARN pass)

**Research doc:** §1.5 scorecard row 1 (VERIFY = objective gate — *"PARTIAL, biggest gap"*),
§2 T12(a), §3 Step 1.5. The core Loop-Engineering warning ("two optimists agreeing" is not a gate)
applied to our own `orchestrator.py:781` + `enable_llm_judge=False`.

**Problem in one line:** Where a ship decision rests on **LLM judges / consensus agreeing** with no
test/build/diff/runtime witness underneath it, we are shipping on opinion, not proof. We don't
currently even *know* how often that happens.

**Claude Code primitive (verified):** the enforced form of this gate is a **blocking `Stop` or
`PostToolBatch` hook** in `.claude/settings.json` that runs the objective witness (test suite / `node
--check` / build) and blocks on non-zero exit (`decision:"block"` / exit 2) — the docs give this exact
test-suite-blocker example ([hooks](https://code.claude.com/docs/en/hooks)). Overmind's own verifier is
the Python analog; the shadow classifier below is the audit that decides *which* task types earn that hook.

### Concrete first step (smallest safe change — pure observation, zero behavior change)
Add a **read-only classifier** that, for every verification result the orchestrator produces, records
which **named objective witnesses** actually contributed to the verdict vs. which verdicts leaned on
judge/consensus alone. Emit a `WOULD-SHIP-WITHOUT-OBJECTIVE-GATE` **WARN** span/log line when the
success verdict has **no** objective witness in its `completed_checks` — but **do not change the verdict**.

Objective witnesses to recognize (all already exist in the codebase — this is a taxonomy, not new gates):
- test-suite exit-code witness, `node --check`, build witness (`verifier.py` allowlist + exit codes)
- Playwright / browser runtime (`browser_checks.py`)
- byte-diff / numeric-diff / numerical-continuity witnesses
- RapidMeta R-parity + benchmark-regression gate
- Sentinel BLOCK (fail-closed) as a negative gate

"Non-objective" = the verdict's deciding check is `semantic_requirements` (the LLM judge path at
`orchestrator.py:775-790`) or a quorum/consensus vote with none of the above present.

### Files / components it touches
- **`core/orchestrator.py`** — the verdict assembly around `:775-819`. Add a classifier that inspects
  `required_checks` / `completed_checks` / `skipped_checks` (already threaded here) and tags the result.
  **No control-flow change in step 1** — only a computed label + WARN emission.
- **`verification/verdict_trace.py`** (via Step 1/T3) — carry the `objective_gate_present: bool` and
  `deciding_check` fields on the span so the WARN is queryable, not just logged.
- A small standing map of **task-type → required objective witness** (new config file, additive), so
  the audit knows which witness a given task type *should* have. Start it in
  `config/` alongside existing policy config; seed it read-only.

### Objective gate that proves *this* works (meta-gate)
Run one full nightly with the classifier on. It passes if it produces a **non-empty, plausible
tally**: "N of M success verdicts had an objective witness; K relied on consensus alone," and the K
list is manually spot-checkable against known judge-only task types. Success = the number is
**produced and believable**, not that it is zero.

### Rollback
Remove/disable the classifier flag (`OVERMIND_OBJECTIVE_GATE_AUDIT`, default `shadow`). It never
touched a verdict, so rollback is a no-op to ship behavior.

### Done-check
- [ ] Classifier runs in shadow across one nightly, emits per-verdict `objective_gate_present`.
- [ ] Dashboard/log shows the "% of ships resting on consensus-without-a-floor" number.
- [ ] Spot-check ≥5 flagged verdicts by hand — the WARN fires on genuinely judge-only ships and
      **not** on ships that had a real test/build/diff witness (no false WARNs).

### Promotion path (only after the WARN cycle quantifies the gap — research doc §3 Step 1.5)
1. **Cycle 1:** WARN-only. Measure how many ships rely on consensus alone.
2. **Cycle 2 decision, per task-type:** either (a) require the named objective witness (verdict
   becomes FAIL/`UNVERIFIED` without it — reuse the existing `UNVERIFIED` verdict, never a silent
   pass), or (b) reclassify the task as **human-in-the-chair** (not loop-eligible).
3. Never promote a task-type to blocking without the WARN-cycle evidence for it.

### Ordering / risk
- **Depends on:** Step 1 (T3 tracing) for clean emission, but can log standalone if needed.
- **Risk:** Very low in WARN mode (observational). The *only* behavior-changing part (promotion to
  blocking) is deferred behind a measured cycle and reuses the existing `UNVERIFIED` verdict, so it
  can never silently flip a PASS. **Adopt-today** for the WARN pass.

---

## ★ TOP MOVE #2 — T11: Claude-maker + Codex-checker cross-vendor QA lane (NOW UNBLOCKED)

**Research doc:** §1.5 scorecard row "Maker/checker" (PARTIAL → strong once Codex re-authed),
§2 T11, §3 Step 3.5. **Status change since the doc was written:** the doc lists this as
*hard-blocked* on both Codex seats being 401-revoked. **That prerequisite is now met** — Codex has
been re-authed on pc1 and we have already run a working cross-vendor witness + bug-hunt this session
(per session notes / memory `cross-engine-corroboration-2026-06-25`). **The lane is therefore
adopt-today, additive, advisory-only.**

**Live-code reality (verified today):** `CodexBackend` already supports everything the lane needs
*except a reasoning-effort control*:
- per-seat `CODEX_HOME` via `OVERMIND_CODEX_HOME_<SEAT>` (mahmood/noreen) — `judge_backends.py:107-113`
- `codex exec --skip-git-repo-check --sandbox read-only -` — `judge_backends.py:119`
- Windows `.CMD`/`.BAT` → `cmd /c` wrapper — `judge_backends.py:121-123`
- `available()` gates on `shutil.which(codex)` + `CODEX_HOME` dir existing — `judge_backends.py:114-115`

**Claude Code primitive (verified):** the checker is a **subagent** (`.claude/agents/codex-reviewer.md`)
with `tools: Read, Grep, Glob` + a `Bash(codex exec *)` allowance, or equivalently an **`agent`-type
hook** on `SubagentStop`/`PostToolBatch` that shells to `codex exec`; per-subagent `model`/`effort`
frontmatter maps to the low-smoke / xhigh-real split ([sub-agents](https://code.claude.com/docs/en/sub-agents),
[hooks](https://code.claude.com/docs/en/hooks)). In Overmind's Python substrate the equivalent is the
`CodexBackend` lane below — same pattern, our runtime.

### Concrete first step (smallest safe change — additive, advisory WARN, tiny surface)
**Step 1a — wire a reasoning-effort knob into `CodexBackend` (the one missing piece).**
Add an optional `effort: str` field to `CodexBackend` that appends `codex`'s config override for
reasoning effort (e.g. `--config model_reasoning_effort=<low|xhigh>` per the codex CLI) to `argv`.
Default `effort=None` = **current behavior byte-for-byte** (so existing judge paths are untouched).
Use it as: **`low` for the smoke/availability probe, `xhigh` for a real bug-hunt pass.**

**Step 1b — stand up the lane as an advisory stage.**
Add a Codex bug-hunt persona/lane in `review/multi_persona.py` (which already enforces
**reviewer-runner ≠ writer-runner** via `preferred_runner_for`, `multi_persona.py:52-61`) and wire it
into the nightly verification phase as a **WARN-only** producer. Findings land in
`sentinel-findings`-style advisory output — **never ship-blocking** on cycle 1. Because it is a
*different vendor's* review, it decorrelates from our Claude-heavy judge panel (the strongest reason
to keep it — research doc §2 T11).

### Files / components it touches
- **`verification/judge_backends.py`** — add `effort` field + argv append to `CodexBackend.query`
  (additive; `None` default preserves current behavior). This is the only change to a live judge class.
- **`verification/judge_factory.py`** — the `codex` / `codex-noreen` seats are already registered
  (`:56-57`) and `enforce_distinct_families` (`:148`) already keeps the panel cross-vendor. The lane
  reuses these; no change needed for decorrelation.
- **`review/multi_persona.py`** — add the "Codex bug-hunter" persona; reuse `preferred_runner_for`
  cross-model dispatch so the checker is never the same runner that wrote the code.
- **`nightly/runner.py`** — register the lane in the verification phase as an advisory producer
  (WARN sink), behind `OVERMIND_CODEX_BUGHUNT_LANE` (default off → then shadow).
- **Cluster (optional, later):** dispatchable per-node via the cluster harness for the RapidMeta
  engine (~31 JS engines / ~14k lines) — but only after Step 3/4 make the cluster safe. Not cycle 1.

### Seat / effort configuration (concrete, from live code + research doc)
- **Two seats, isolated homes:** `OVERMIND_CODEX_HOME_MAHMOOD` and `OVERMIND_CODEX_HOME_NOREEN`
  (or default `~/.codex` / `~/.codex-noreen`) — already how `_codex_home()` resolves. Keep seats on
  separate `CODEX_HOME` so a re-auth of one never clobbers the other.
- **`--skip-git-repo-check`** — already always passed; required so the read-only judge runs against a
  worktree/sandbox that isn't a clean git repo. Keep.
- **Effort tiers:** `low` for the availability smoke probe (fast, cheap — is the seat alive and does
  `codex exec` respond?), **`xhigh` for the real bug-hunt pass** (research doc names Codex as our
  strongest bug-finder; spend the tokens only on the real pass).

### Objective gate that proves it works
1. **Smoke (low effort):** `codex exec` responds with a well-formed answer on a canned prompt for
   **both seats** — no 401, no timeout. (This is the auth-attestation smoke; folds into T5.)
2. **Real (xhigh effort):** on a **known-buggy fixture** — the RapidMeta `P0-denominator-logic`
   family (events > N, e.g. `CAPLACIZUMAB_TTP cE=524 > cN=39`, research doc §1.4) — the Codex lane
   **flags the arithmetically-impossible 2×2 cell**. If it catches the known planted bug, the lane
   has signal. This is a *concrete, non-fabricated* regression target that already exists on disk.

### Rollback
Unset `OVERMIND_CODEX_BUGHUNT_LANE` → the lane produces no output; every existing path is unchanged.
The `effort` field defaults to `None` → `CodexBackend` reverts to today's exact argv. Two-flag,
fully reversible.

### Done-check
- [ ] `CodexBackend(effort="low")` and `effort="xhigh")` both produce the expected argv (unit test);
      `effort=None` is byte-identical to today.
- [ ] Both seats pass the low-effort smoke probe (auth live — this is the doc's prerequisite, now met).
- [ ] xhigh lane run over the RapidMeta denominator fixture flags the planted `cE>cN` bug.
- [ ] Findings land as advisory WARN only; a deliberately-false finding does **not** block a push.
- [ ] One full advisory cycle recorded; no ship path changed.

### Promotion path
Promote a **finding class** (not the whole lane) to blocking only after it proves itself over a cycle —
the `P0-denominator-logic` family is the obvious first candidate (research doc §3 Step 3.5). Gate the
live lane behind **T5 auth attestation** so a silently-expired seat downgrades to `AUTH_DEGRADED`
rather than passing an empty review.

### Ordering / risk
- **Depends on:** Codex re-auth (✓ done). Benefits from T5 (Step 3) for the AUTH_DEGRADED guard, but
  does not require it for the advisory cycle.
- **Risk:** Low by design — advisory, additive, cross-vendor. **Adopt-today.**

---

## Step 0 — Portable paths (prerequisite hygiene — blocks non-C: shadow runs)

**Research doc:** §3 Step 0; §1.1 weak point (hardcoded `C:/overmind/...`).
- **First step:** Replace hardcoded `C:/overmind/...` literals with config-derived paths.
- **Files:** `nightly/runner.py` (doc cites `:736,934,952,973,1103,1309`). Verify each with
  `grep -n "C:/overmind\|C:\\\\overmind" nightly/runner.py` before editing.
- **Objective gate:** existing test suite passes **and** a dry nightly launches with cwd on `F:\`
  (or a sandbox) without a path error. Pure refactor.
- **Rollback:** it's a refactor covered by existing tests; revert the commit.
- **Done-check:** grep shows zero hardcoded `C:/overmind` in the ship path; nightly resolves paths
  from config on both `C:` and `F:`.
- **Ordering:** **first** — gates every shadow run that must execute off `C:`. **Adopt-today.**

---

## Step 1 — Observability ON + loop economics (T3 + T12b)

**Research doc:** §2 T3, §2 T12(b), §3 Step 1.
- **First step:** Thread the existing `verdict_trace.py` tracer through the orchestrator/verifier/
  judge hot paths (today most callers pass `tracer=None`). Simultaneously emit **cost-per-accepted-
  change** and **acceptance-rate per loop** (tokens-per-accepted-fix). Both side-effect-free.
- **Files:** `verification/verdict_trace.py`, `core/orchestrator.py`, `cluster/scheduler.py`.
- **Objective gate:** dashboards show **non-empty spans** and a **cost-per-accepted number** for one
  nightly; the acceptance-rate metric flags any loop below the ~50% practitioner break-even
  (heuristic, *not* a measured constant — research doc §1.5 truth-first note).
- **Rollback:** tracer defaults to no-op; metrics are additive emission only.
- **Done-check:** one nightly produces queryable spans + a cost-per-accepted figure per loop.
- **Ordering:** right after Step 0; **prerequisite for A/B-testing Steps 2–5.** **Adopt-today.**

---

## Step 1.5 — Objective-gate audit (T12a) + anti-drift reread (T12e)

**T12a is TOP MOVE #1 above** — full detail there. In the same step, add **T12e anti-goal-drift**:

**T12e — standing AGENTS.md / goal reread at loop start**
- **First step:** At each loop-run entrypoint, re-read the governing AGENTS.md/goal file and inject it
  into the run context before work starts (cheap, additive). Counters long-session goal drift
  (research doc §1.5 failure modes).
- **Files:** the loop entrypoints / SKILL.md task runners (research doc §2 T12 maps e,g to "loop
  entrypoints / SKILL.md tasks").
- **Objective gate:** a loop run's context provably contains the current AGENTS.md hash/content
  (log the reread + hash). Trivially verifiable.
- **Rollback:** remove the reread hook; no state to unwind.
- **Done-check:** every loop run logs an AGENTS.md reread with a content hash.
- **Ordering / risk:** low-risk, additive. **Adopt-today.**

---

## Step 1.6 — Give each recurring lane the Loop-Library treatment (T-LL) — adopt-today

**Source (verified 2026-07-04 by fetching the page):** Forward Future — **Loop Library**,
https://signals.forwardfuture.com/loop-library/ . A curated set of repeatable agent loops, each
stated as *objective + proof + explicit STOPPING CONDITION*. The exact stop conditions quoted below
were read off the live page. This directly operationalizes the research doc's Loop-Engineering thesis
(§1.5): every one of our recurring jobs should be expressible as **objective gate + proof artifact +
stop condition**, not an open-ended "keep going."

**First step (smallest safe change — spec only, no runtime change):** write a one-page **loop spec**
(SKILL.md-style) for each recurring lane, each borrowing the closest Loop-Library template's *proof*
and *stop condition* verbatim as its acceptance contract. This is documentation that makes the loop's
gate and stop explicit **before** any automation — the build-order rule (manual-reliable → Skill →
loop → schedule) demands the spec exists first.

**The 3–5 templates that directly fit our lanes** (template → our lane → adopted proof + stop):

| Loop-Library template (quoted) | Our lane | Proof artifact | Stop condition (adopted verbatim) |
|---|---|---|---|
| **Multi-LLM convergence loop** — *"Ensures two different AI systems approve identical work"* | Methods **cross-vendor witness** loop (Claude + Codex/agy) | both engines' verdicts on one unchanged artifact | *"only when both approve the same unchanged version"* |
| **Clodex adversarial-review loop** — *"Uses independent reviewer to challenge PRs until issues resolve"* | **T11 Codex-checker** lane (Top Move #2) | Codex bug-hunt findings; accepted-findings ledger | *"when Codex approves, only accepted findings remain, progress stalls, or iteration cap is reached"* |
| **Quality streak loop** — *"Eliminates product failures through realistic test scenarios"* | **RapidMeta QA** loop | *"document it, add regression and benchmark coverage, fix it"* | *"After [N] successful cases in a row"* |
| **Production error sweep** — *"Identifies and verifies actionable errors"* | RapidMeta / methods **error sweep** | root-cause trace + verified fix | *"If no actionable errors are present, stop without making changes"* |
| **Research-to-artifact loop** — *"Transforms focused research into decision-ready sourced documents"* | **Journal-upgrade** loop | *"important claims trace to sources, and remaining uncertainty is explicit"* | *"when the artifact meets its acceptance criteria"* or *"blocked or exhausted"* |
| **Post-release baseline loop** / **recovery proof loop** — *"Benchmarks completed releases"* / *"Verifies real backups restore"* | **Clinic monitoring** loop | recorded reproducible baseline; per-scenario restore proof | *"when every scenario reaches its predefined consecutive-success streak"* |

**Why these five are the right pull:** the two review loops (convergence, Clodex) are *exactly* our
T11 cross-vendor pattern — the Clodex template even names Codex as the adversarial reviewer, and its
stop condition (**"iteration cap is reached"**) supplies the hard STOP that T12c/§1.5 says our
per-loop stops are missing. The quality-streak and error-sweep templates give the RapidMeta QA lane a
**streak-based** stop (N-in-a-row) and a **clean-exit** stop (nothing actionable → stop, don't churn)
— both of which the RapidMeta `P0-denominator-logic` at-scale bug shows we currently lack. The
research-to-artifact template's proof (*every important claim traces to a source; uncertainty is
explicit*) is the acceptance contract this very checklist and the source research doc already follow.

**Files / components:** new SKILL.md-style loop specs under the loop entrypoints / `SKILL.md` task
area (research doc §2 T12 e/g surface); each references its objective witness (T12a), and the methods
+ Codex specs reference the T11 lane. **No runtime code changes in this step** — specs only.

**Objective gate that proves it works:** each of the ≥5 lane specs names (a) a concrete objective
witness, (b) a proof artifact, and (c) a terminal stop condition drawn from a cited Loop-Library
template — reviewable on one page, no open-ended loop remaining.

**Rollback:** specs are documentation; deleting a spec reverts to today's ad-hoc lane.

**Done-check:**
- [ ] RapidMeta QA, methods cross-vendor, Codex-checker, journal-upgrade, and clinic-monitoring lanes
      each have a one-page spec with objective gate + proof + stop.
- [ ] Each stop condition is bounded (streak, cap, clean-exit, or convergence) — none is "run forever."
- [ ] Methods + Codex specs cross-reference the T11 lane and T12a objective-gate audit.

**Ordering / risk:** low (documentation), and it *sharpens* T11 + T12a by giving them named stop
conditions. **Adopt-today.** Depends on nothing; strengthens Steps 1.5 and 3.5.

### Reusable skill patterns to start from: Matt Pocock's skills repo

**Source (verified 2026-07-04 by fetching the repo):** Matt Pocock — **skills**,
https://github.com/mattpocock/skills — a curated collection of agent/Claude Code skills. Rather than
author every lane skill from scratch, adapt these **verified** entries (names + descriptions quoted from
the repo README) as the starting shape for our loop templates:

| mattpocock skill (verified) | Maps to our lane / T-item | How we adapt it |
|---|---|---|
| **`tdd`** — *"Test-driven development with a red-green-refactor loop… one vertical slice at a time"* | The **inner "make tests pass" loop** (LFD spec-driven inner loop) under any lane | The canonical objective-gate inner loop; pairs with T12a (the gate must be real) |
| **`diagnosing-bugs`** — *"Disciplined diagnosis loop for hard bugs… reproduce → minimise → hypothesise → instrument → fix → regression-test"* | **Production error sweep** lane (T-LL) + **T8** failure→regression | Its "regression-test" terminal step *is* T8's auto-promote-to-fixture; its stop = clean reproduce |
| **`code-review`** — *"Two-axis review of the diff… **Standards**… and **Spec** (does it faithfully implement the originating issue/PRD?)"* | **Cross-vendor witness / Codex-checker** lane (T11, T-CV) | Run the *Spec* axis as the different-vendor checker's rubric; the two-axis split decorrelates from a pure bug-hunt |
| **`to-prd`** / **`grill-with-docs`** — *"Turn the conversation into a PRD…"* / *"…builds your project's domain model… updating `CONTEXT.md` and ADRs"* | **Journal-upgrade** lane (T-LL) + **T-LFD** loss-spec authoring | The grilling pattern is how we write each lane's loss function (target/fences) rigorously before automating |
| **`triage`** — *"Move issues through a state machine of triage roles"* | **Clinic monitoring** + **T12g** build-order governance | Formalizes the lifecycle-status state machine (Active/triage/unverified) our registry rules already imply |
| **`improve-codebase-architecture`** — *"Scan… for deepening opportunities… visual HTML report"* | **RapidMeta QA** deep-scan pass | A scheduled deep-scan variant; findings feed the QA lane's regression coverage |

**Truth-first:** I verified these skills exist in the repo and quoted their descriptions; I did **not**
audit their internal implementation — treat them as **starting patterns to adapt**, not drop-in
production components. Each still gets our objective gate + stop condition + LFD fences layered on.

**Also: sanyuan0704/sanyuan-skills — production-grade skills + the meta-tooling to author ours well.**
**Source (verified 2026-07-04 by fetching the repo):** https://github.com/sanyuan0704/sanyuan-skills
(**MIT, ~3.7k★**), 6 skills. Verified names + descriptions:

| sanyuan skill (verified) | Maps to our use | How we use it |
|---|---|---|
| **Code Review Expert** — *"Senior engineer code review covering SOLID, security, performance, error handling"* | Another concrete impl of the **different-vendor / checker gate** (T11, T-CV) | A second reviewer rubric to run in the cross-vendor checkpoint — complements the two-axis `code-review` and the Codex bug-hunt |
| **Skill Forge** — *"Meta-skill for creating high-quality skills with 12 battle-tested techniques"* | The way we **AUTHOR** our loop-template skills | Use it to write the RapidMeta-QA / methods / journal / clinic lane skills well the first time (write-once, high-quality) |
| **Skill Review** — *"Quality audit for skills: structure, description, workflow, token efficiency, anti-patterns"* | The way we **AUDIT** those skills | Run it over each authored lane skill — token-efficiency matters (part-6 "keep skills SHORT", bloat paid every beat) |
| **Wiki Ingest** — *"Compile articles, documents, or notes into a structured, cross-referenced wiki knowledge base"* | The **shared knowledge base** angle (pairs with MemClaw + the Vault section below) | Auto-compile our methods + RapidMeta knowledge into the vault |
| **Sigma / Book Study** (learning) | — | not lane-relevant; noted for completeness |

> **⚠ Security caveat (same as mattpocock, non-negotiable):** these are **third-party skills that run
> instructions inside the agent.** **AUDIT the skill contents before install** — read every `SKILL.md`
> and any scripts it references; do not trust-on-faith. Skill Review is itself a useful auditor, but a
> human read of the skill body precedes install. This matches the research doc's Sentinel plugin-loader
> warning (arbitrary code at push time) and our truth-first bar.

- **Objective gate:** at least the cross-vendor (`code-review`), error-sweep (`diagnosing-bugs`), and
  inner-loop (`tdd`) lanes are seeded from an adapted mattpocock skill rather than written cold.
- **Done-check:** each adapted skill is committed as a `.claude/skills/<lane>/SKILL.md` with our gate +
  stop + fences added; provenance (which mattpocock skill it derives from) noted in the spec.

### Copy-pasteable `/loop` specs — the 6-part anatomy on real Claude Code commands

**Source (practitioner guide):** AI Edge (@aiedge_) beginner's Loop Engineering guide, referencing Boris
Cherny's loop pattern and Fable 5. **Truth-first:** it's a practitioner guide, and I verified its
command claims against the Claude Code commands reference before restating them — **all real:**
`/loop [interval] [prompt]` (bundled skill; omit interval → Claude self-paces; reads `.claude/loop.md`;
alias `/proactive`), `/goal [condition]` (*"Claude keeps working across turns until the condition is
met"*, [goal docs](https://code.claude.com/docs/en/goal)), `/schedule` (cloud routines, alias
`/routines`), `/compact` (summarize to free context), `/effort [low|medium|high|xhigh|max]` — all in
[commands](https://code.claude.com/docs/en/commands). *One flag:* the guide's detail that `/goal` runs a
**separate fast model to grade each turn** is the guide's description; the docs confirm the
work-until-condition behavior but I did not verify the "separate fast grader" mechanism — treat that
specific detail as practitioner framing.

**The goal-condition mindset:** a normal prompt says **WHAT** to do; a `/loop`+`/goal` says **WHEN to
STOP** — a *verifiable end state*. **6-part loop anatomy, mapped 1:1 to our building blocks:**

| Loop-anatomy part | Claude Code mechanism (verified) | Our building block |
|---|---|---|
| **1. TRIGGER** | `/schedule` (cloud cron) or `/loop [interval]` (self-paced if omitted) | Automation/heartbeat (T12); nightly runner |
| **2. EXECUTION** (doer) | the main agent / a subagent | the lane's implementer |
| **3. VERIFIER** | `/goal` grades each turn; tests/build/screenshot as the gate | **objective gate (T12a)** + **different-vendor check (T-CV/T11)** |
| **4. STOP RULES** | explicit success + failure + token/$ budget in the goal text | **hard stops (T12c)** + LFD constraints |
| **5. MEMORY** | `progress.md` read at start, updated at end | our `PROGRESS.md` convention + shared store (T12f/MemClaw) |
| **6. SKILLS** | `CLAUDE.md` / skills, **kept SHORT** (bloat paid every beat) | T-LL lane skills + T12e reread |

**Standard template to fill per lane:**
> `/loop [verifiable end state], only touching [scope], stop after [X iterations or $budget], use [skill],
> use verifier agents for [checkpoint], keep a memory file at [path].`

**The four recurring jobs, rewritten as filled-in `/loop` goal-conditions** (design templates — the
referenced skills are the ones authored per T-LL/T-LFD; paths follow the gitignored `PROGRESS.md`
convention):

```text
# (a) RapidMeta QA loop
/loop until every generated dashboard passes the denominator fence (events <= N) and the R-parity gate,
  only touching F:\rapidmeta-finerenone (engines + generated dashboards),
  stop after max 20 iterations OR $15 spend — whichever first;
  if 50 dashboards validate in a row report TASK_COMPLETE and stop;
  after 3 unrecoverable retries report TASK_FAILED:[reason] and stop,
  use the rapidmeta-qa skill (byte/numeric diff + R-parity + benchmark-regression gate),
  use a DIFFERENT-VENDOR verifier agent (Codex, xhigh) for the 2x2-cell / denominator-logic checkpoint
    — a found-nothing pass must FAIL the planted cE>cN canary,
  keep a memory file at F:\rapidmeta-finerenone\PROGRESS.md.

# (b) Methods cross-vendor witness loop
/loop until Claude AND a different-vendor witness approve the SAME unchanged artifact (multi-LLM convergence),
  only touching the methods repo under test (no writes outside it),
  stop after max 10 convergence rounds OR $10;
  if both vendors approve the unchanged version report TASK_COMPLETE and stop;
  if no convergence after 10 rounds OR progress stalls report TASK_FAILED:[reason] and stop,
  use the methods-objective-gate skill (test-suite + node --check + numeric-continuity witness),
  use verifier agents Codex (xhigh) AND agy for the cross-vendor sign-off checkpoint (reviewer != writer),
  keep a memory file at <methods-repo>\PROGRESS.md.

# (c) Journal-upgrade loop
/loop until every important claim traces to a source and remaining uncertainty is stated explicitly
    (research-to-artifact acceptance),
  only touching the target manuscript/journal document (no code, no data files),
  stop after max 15 iterations OR $12;
  if the acceptance criteria are met report TASK_COMPLETE and stop;
  if blocked or exhausted report TASK_FAILED:[reason] and stop,
  use the journal-upgrade skill (citation-trace + claim-fidelity check),
  use a DIFFERENT-VENDOR verifier agent (Codex or agy) for the citation/claim-fidelity checkpoint
    (guards the academic-integrity reward-hack: swapped/generic refs),
  keep a memory file at <doc-dir>\PROGRESS.md.

# (d) Clinic monitoring loop
/schedule daily: /loop until every monitored scenario reaches its predefined consecutive-success streak
    (reproducible baseline recorded),
  only touching the clinic monitors + baseline records (read-only on production dashboards),
  stop after max 8 checks per run OR $5;
  if every scenario hits its streak report TASK_COMPLETE and stop;
  if any scenario fails N times report TASK_FAILED:[scenario] and stop,
  use the baseline/recovery-proof skill (standard benchmarks + integrity + representative read/write),
  use a DIFFERENT-VENDOR verifier agent for any flagged anomaly (spot-check before alerting),
  keep a memory file at <clinic-dir>\PROGRESS.md.
```

**Pro-tips baked into every spec above (from the guide; sound practice):**
- **Always cap BOTH iterations AND dollars** — never one without the other (a per-iteration cheap loop
  can still run away on count; a few-iteration loop can still burn budget on `xhigh`).
- **Default reasoning effort `high`; reserve `xhigh` for complex checkpoints only** (`/effort` verified;
  here the different-vendor verifier runs `xhigh`, the doer stays `high`).
- **Subagents get fresh context** — the different-vendor checker starts clean, which is *why* it
  decorrelates (T-CV) and doesn't inherit the doer's blind spots.
- **`/compact` before long runs** — keep `CLAUDE.md`/skills SHORT (bloat is paid every beat, part 6 of
  the anatomy); the T12e AGENTS.md reread stays lean for the same reason.

**Objective gate for these specs:** each of the four lanes has a filled-in `/loop` block with (1) a
verifiable end state, (2) an explicit success string (`TASK_COMPLETE`), (3) an explicit failure string
(`TASK_FAILED:[reason]`), (4) both an iteration cap and a `$` cap, (5) a named quality-gate skill, (6) a
named different-vendor verifier checkpoint, and (7) a `PROGRESS.md` path. **Done-check:** the four blocks
above are committed into the lane specs; every `[skill]` and `[verifier]` referenced exists (or has an
owning T-item to build it). **Adopt-today** (specs), grounded in verified commands.

---

## Step 2 — Subprocess watchdog (T1) + Sentinel per-rule watchdog (T2)

**Research doc:** §2 T1, §2 T2, §3 Step 2. **Shadow → enforce.**

**T1 — universal subprocess watchdog (timeout + tree-kill + bounded jittered retry)**
- **First step:** Extend `subprocess_utils.py` into the single wrapper for every external-process
  call: hard wall-clock timeout, **process-tree kill on expiry** (the proven
  `kill_process_tree()`/`taskkill /F /T` already there — verified today), capped retries with
  exponential backoff + jitter, and a structured `TOOL_TIMEOUT`/`TOOL_ERROR` result. Ship in
  **shadow (log-only):** record what *would* have been killed/retried; act on nothing.
- **Files:** consolidate through `subprocess_utils.py`; callers `verification/judge_backends.py:49-62`
  (180s no-retry runner), `cluster/transport.py:122-131` (blocking `subprocess.run`), Sentinel rule
  execution (see T2).
- **Objective gate (A/B):** one full nightly + one week of pushes — the watchdog path must show
  **zero verdict deltas** vs. the current path (only genuinely-hung processes differ). Then flip to
  enforce.
- **Rollback:** unset `OVERMIND_SUBPROC_WATCHDOG`; old code path untouched.
- **Done-check:** shadow log shows would-kill/would-retry events; verdict-delta = 0; then enforced.

**T2 — Sentinel per-rule execution watchdog (ReDoS containment)**
- **First step:** Run each `rule.check(ctx)` under a wall-clock cap in a killable worker; on timeout
  emit `RULE_TIMEOUT` **WARN** and continue (never silently *block* a push). Shadow first by logging
  per-rule durations for a week to pick a threshold that never false-trips a legitimately slow rule.
- **Files:** Sentinel `scan.py:188-194`, `yaml_loader.py:121-123` (in `F:\Sentinel`).
- **Objective gate:** a planted catastrophic-backtrack pattern is **contained to a WARN** instead of
  hanging the pre-push hook; no legitimately-slow rule false-trips at the chosen threshold.
- **Rollback:** unset `SENTINEL_RULE_TIMEOUT_MS` (unset = current behavior).
- **Done-check:** ReDoS fixture → `RULE_TIMEOUT` WARN, push completes; duration histogram justifies
  the threshold.
- **Ordering / risk:** low; fail-open to WARN. **Needs validation** (shadow week) before enforce.

---

## Step 3 — Auth preflight (T5) + per-node breaker/backoff (T6) — cluster branch, shadow

**Research doc:** §2 T5, §2 T6, §3 Step 3. Validate on the (unmerged) cluster branch.

**T5 — fail-fast auth preflight + capability attestation before quorum**
- **First step:** Before assembling a judge quorum or dispatching to a node, probe each backend/node
  for **live auth** (does `claude -p` respond? is the codex seat 401?) and refuse to *advertise* a
  family/node it can't use — emit `AUTH_DEGRADED` instead of silently running a 1-engine quorum.
  Shadow: log the attestation verdict without acting for a week; confirm it matches reality.
- **Files:** `verification/judge_factory.py` (currently trusts `available()`); cluster
  `transport.py:71-83` (transient-vs-permanent misclassification). Reuse the `CodexBackend.available()`
  pattern + a low-effort `codex exec` smoke (shared with T11 Step 1a).
- **Objective gate:** with a deliberately dead key, the attestation reports `AUTH_DEGRADED` and the
  quorum advertises only live families — matching reality with **no false rejects** over the shadow week.
- **Rollback:** flag flip; quorum reverts to trusting `available()`.
- **Done-check:** dead-key fixture → `AUTH_DEGRADED`, no silent 1-engine quorum.

**T6 — per-node circuit breaker + backoff/jitter on requeue**
- **First step:** Extend the existing project-level `NightCircuitBreaker` (`verification/loop_brakes.py`)
  to **nodes**, and add exponential backoff + jitter to `cluster/scheduler.py:200`'s immediate requeue;
  let an offline-marked node be re-probed once its breaker half-opens.
- **Files:** `cluster/scheduler.py:180-213`, reuse `verification/loop_brakes.py`.
- **Objective gate:** a deliberately flapping-node fixture no longer produces back-to-back retry
  storms; a transient blip does not remove a node for the whole batch (re-probe on half-open).
- **Rollback:** flag flip; requeue reverts to immediate.
- **Done-check:** flapping-node fixture shows backoff+jitter and half-open re-probe.
- **Ordering / risk:** low (reuses battle-tested breaker), but **validate on the flapping fixture**.

---

## Step 3.5 — T11 Codex-checker lane + T-CV mandatory cross-vendor check — **TOP MOVE #2 above** (adopt-today, Codex now live)

Full detail in TOP MOVE #2. Prerequisite (Codex re-auth on pc1) is **met**. Gate the live lane behind
T5's attestation (Step 3) once available so an expired seat downgrades to `AUTH_DEGRADED`.

**In the same step, land T-CV** (defined in the Framing section, validated by TRINITY): make a
**different-vendor check-before-ship** a *required, recorded* step in the nightly verification phase.
The **check is mandatory** (record "cross-vendor check present, vendor=…" on every ship verdict; absence
is a WARN via T12a); the **finding stays advisory** for the first cycle so a false positive never
blocks a push. `enforce_distinct_families` guarantees the checker family ≠ the maker family — this is
our own decorrelation rule, reinforced by TRINITY's team-of-models result. Flag
`OVERMIND_REQUIRE_CROSS_VENDOR_CHECK` (default record-only).

---

## Step 4 — Durable dispatch journal (T4) + bounded escalation ceiling (T10-escalation)

**Research doc:** §2 T4, §2 T10 (escalation half), §3 Step 4. **Needs validation.**
- **First step:** Append-only jsonl journal of node assignments + verdicts on the cluster branch;
  replay on restart with **idempotent dedup** to skip completed jobs. Start **journal-only** — do NOT
  bolt on Temporal/DBOS (research doc explicitly defers the full runtime).
- **Then:** implement SGH's **three-level escalation** (L1 bounded Retry → L2 Local Patch → L3 Replan)
  as the formal ceiling over T1/T6's retry/breaker logic.
- **Files:** `cluster/registry.py:113` (in-memory `NodeState` SPOF); scheduler retry path.
- **Objective gate:** inject a mid-batch dispatcher crash — a resumed run must **not double-execute** a
  completed job, and recovery must **terminate at the escalation ceiling** instead of looping.
- **Rollback:** journal is additive (append-only file); disable replay to revert to in-memory.
- **Done-check:** injected-crash test passes (no double-exec, bounded recovery). *Only after green*
  is the cluster branch a merge/CI candidate — enforcing T12g build-order governance.
- **Ordering / risk:** medium (idempotency can double-execute if dedup is wrong). **Validate first.**

---

## Step 4.5 — Shared signal store (T12f)

**Research doc:** §2 T12(f), §3 Step 4.5.
- **First step:** Generalize the working `STUCK_FAILURES.jsonl` → Overmind witness link into a small
  **append-only signal bus** the RapidMeta / methods / clinic loops write to and read from. Start
  **read-only** (consumers subscribe; no loop changes behavior on another's signal until validated).
- **Files:** the Sentinel↔Overmind JSONL contract (`STUCK_FAILURES.jsonl` already read by Overmind).
- **Objective gate:** a signal written by one loop is readable by another with correct schema; no
  consumer changes its verdict on a subscribed signal yet (read-only phase).
- **Rollback:** consumers ignore the bus; producers keep writing their own JSONL as today.
- **Done-check:** cross-loop read demonstrated; zero behavior change in read-only phase.
- **Ordering / risk:** low, additive. **Adopt-today (read-only).**

### Recommended concrete tool: Caura **MemClaw** (governed shared memory) — shadow-first, file-state is the floor

**Source (verified 2026-07-04 by fetching the repo):** Caura **MemClaw**,
https://github.com/caura-ai/caura-memclaw (also https://memclaw.net/ ) — **Apache-2.0**, *"Fleet memory
for AI agents — governed, shared, self-improving."* **Verified README features:** MCP-native (built-in
Model Context Protocol at `/mcp`); **visibility scopes** (`scope_agent` private / `scope_team`
fleet-wide, stamped at write time); **trust tiers** (four levels gating cross-fleet read/write/delete);
**keystone policies**; **full audit log** (every write/delete/transition logged); **tenant isolation**
(row-level DB separation); **contradiction detection** (auto-supersedes conflicting memories);
**auto knowledge graph** (semantic entity resolution auto-merges duplicates); **self-improving
retrieval** (per-agent tuning so search quality compounds). **Production claim (verified as a README
claim, not independently measured by me):** *"In production at eToro (NASDAQ: ETOR): 300+ AI agents on
one governed memory — 26,500+ memories, 1,372 shared skills, 23 ms p50 search."* **Deployment:** a
server/service via Docker Compose or manual Python + PostgreSQL.

**Why it fits our missing shared-signal store:** it is exactly the general append-only, **auditable**,
cross-loop signal bus §1.5 says we lack — and its **MCP-native + full-audit-log** design fits our
truth-first bar (auditable memory, not an opaque cache). It is callable directly as an **MCP server**
from Claude Code hooks (`type:"mcp_tool"`) and headless (`--mcp-config`), so our loops can write/read
signals through the same primitive layer the rest of this plan uses. **Contradiction detection** maps
onto our reward-hacking concern (T-LFD): conflicting signals from correlated loops get surfaced, not
silently merged.

**No-regression adoption path (shadow-first; the working file state stays the floor):**
1. **Shadow / mirror-only.** Stand up MemClaw as a **new, isolated service** and **MIRROR** existing
   state files into it *additively* — `STUCK_FAILURES.jsonl`, `.progress_<date>.json`, `circuit_states.
   json` — **without removing or altering the file-based state.** Every loop keeps writing its JSONL/
   progress files exactly as today; a thin mirror also writes them into MemClaw. **File state remains the
   single source of truth.**
2. **Evaluate quality (read-only consumers).** Measure MemClaw's **recall** and **contradiction-detection**
   against the mirrored ground truth: does a cross-loop query return the right signals? does it correctly
   flag a real contradiction (e.g. RapidMeta says "validated" while the byte-diff says "regressed")? No
   loop changes behavior on a MemClaw read during this phase.
3. **Promote only if it earns it.** Consider making MemClaw the source of truth for a *specific* signal
   class **only after** it demonstrably matches the file state and adds recall/contradiction value —
   and even then, keep the file mirror as a durable floor and audit backstop.

- **Files / components:** a new mirror writer alongside the existing `STUCK_FAILURES.jsonl`/progress
  writers; MemClaw wired as an MCP server (`.mcp.json` / `--mcp-config`); consumers query via
  `mcp__memclaw__*` tools.
- **Objective gate:** for one nightly, every signal in the file state is present and correctly scoped in
  MemClaw, and a seeded contradiction is detected; **zero loop behavior changed** (mirror-only).
- **Rollback:** stop the mirror writer and unwire the MCP server — the file-based state is untouched and
  remains authoritative. Nothing to unwind.
- **Done-check:** MemClaw mirrors ≥3 state-file classes for one nightly with correct scopes + audit
  entries; recall and contradiction quality recorded; file state never demoted.
- **Risks (flag, truth-first):** (a) **a new service to run** — DB + MCP endpoint (note pc2's known
  **socket-buffer fragility**, memory `compute-cluster-nodes`; validate large-payload reads before
  trusting it under load); (b) **governance/config overhead** (scopes, trust tiers, keystone policies
  must be configured deliberately or the audit value is theater); (c) **another dependency** in the
  ship path — hence shadow-first and file-state-as-floor are non-negotiable. **Ordering / risk:** the
  **mirror-only shadow is adopt-today-low-risk**; promotion to source-of-truth is **needs-validation.**

---

## Step 4.6 — Knowledge base / Vault (human-readable memory) — adopt-today

**The three-layer memory model.** Our loops need memory at three resolutions, and they complement rather
than compete:
1. **MemClaw** (Step 4.5) — *machine-readable, governed agent-fleet memory* (scopes, trust tiers, audit
   log, contradiction detection). What the loops write/read as signals.
2. **Vault** (this step) — *human-readable knowledge store*: an **Obsidian-compatible markdown vault**
   (wiki-links `[[note]]`, plain local files). Pairs naturally with Claude Code because both are
   **markdown + file-based** — the same substrate skills, hooks, and `Read`/`Write` already operate on.
3. **Wiki Ingest** (sanyuan skill) — *auto-compile*: turns raw notes/outputs into the cross-referenced
   vault structure.

**Source note (truth-first):** the pairing idea comes from a Fable×Obsidian practitioner tip. **Treat
"Fable is the world's best at long tasks" as an unverified marketing claim** — do not repeat it as fact.
The *design* (a local markdown vault as the human-readable knowledge store) stands on its own and needs
no such claim.

**Why markdown-vault (not a DB) for the human layer:** it is diff-able, git-versionable, greppable,
offline, and editable by both human and agent with zero infra — the same properties that make our
`PROGRESS.md` / research-doc conventions work. MemClaw is the governed machine mirror; the vault is the
readable source humans curate.

**Five concrete workflows to operationalize (each maps to a Claude Code primitive):**

| # | Workflow | What goes in | Claude Code primitive |
|---|---|---|---|
| 1 | **Store every valuable agent output** | plans, research docs, verification reports, manuscripts | a **`Stop` hook** auto-files the turn's output into the vault; or a `research`/`wiki-ingest` skill writes it |
| 2 | **Reusable workflows / SOPs WITH VERSIONING** | the loop-template specs, runbooks — so we can **audit what worked** | vault under **git**; each SOP is a versioned note; **Skill Forge** authors them, **Skill Review** audits |
| 3 | **Curated link / reference library** | the source URLs from this whole checklist (Niklaus, MADE, TRINITY, LFD, Loop Library, CC docs, MemClaw, sanyuan) | **Wiki Ingest** compiles; wiki-links cross-reference |
| 4 | **Competitor / landscape intel** | orchestration systems (Fugu, Terminus-4B, Meta-Harness), benchmark SOTA | a scheduled `research` skill (`/schedule`) appends dated notes |
| 5 | **Swipe file** — reusable copy / prompts | the 4 filled-in `/loop` specs, effective prompts, the loss-function templates | a note the doer skills read via `Read` before composing |

**Claude Code primitive mapping (verified primitives, see Grounding):**
- A **`research` / `wiki-ingest`-style skill** writes structured notes into the vault
  ([skills](https://code.claude.com/docs/en/skills)).
- A **`Stop` hook** can **auto-file** the agent's output into `F:\overmind\vault\` at turn end
  ([hooks](https://code.claude.com/docs/en/hooks) — `Stop` can inject/act; non-blocking use here).
- **MemClaw mirrors the machine-readable side** — the vault note is the human copy; a signal/summary
  is mirrored into MemClaw for cross-loop recall (Step 4.5).

**Live seed (built today):** a **starter vault at `F:\overmind\vault\`** is being seeded from this
session — the implementation checklist, the per-source notes (one note per external source with its
verified facts + truth-first flags), and a reference library of all cited URLs. It is a **knowledge
artifact, not a production system** — outside the Sentinel/Overmind/harness/Dispatch ship path — so
seeding it does not violate the design-only constraint on the *checklist itself*.

- **Objective gate:** the vault opens in Obsidian (or any markdown reader) with working `[[wiki-links]]`;
  ≥1 note exists per external source with its verification status; the reference library resolves.
- **Rollback:** it's a local markdown folder; delete it, nothing else is affected.
- **Done-check:** `F:\overmind\vault\` exists with an index (`README.md`/`_index.md`), per-source notes,
  and the checklist linked in; git-tracked for versioning (workflow #2).
- **Risks (truth-first):** vault drift vs MemClaw (keep the vault human-curated, MemClaw machine-mirror —
  don't dual-source-of-truth the same fact); keep local paths OUT of anything pushed (per lessons:
  `PROGRESS.md`-style content stays gitignored if it carries internal paths). **Ordering / risk:** low,
  additive, human-layer only. **Adopt-today.**

---

## Step 5 — Research track, measurement-gated (T7, T8, T9, T10-DAG)

**Research doc:** §2 T7/T8/T9/T10, §3 Step 5. **Shadow-only against held-out evals / current routing;
must beat the current quorum/loop on *measured* accuracy or produce identical verdicts before touching
any ship path.** Deliberately last — highest upside, only ones that can regress correctness.

- **T7 credibility/debate judge** — `verification/llm_judge.py:576-645`. Shadow vs held-out evals;
  must beat the current `QuorumJudge` on measured accuracy first. **Risk: medium-high** (cost + can
  regress on small keyword-distinct fixtures).
- **T8 failure-taxonomy → regression loop** — `verification/failure_taxonomy.py`,
  `intelligence/eval_harness.py`. Auto-promote classified failures (esp. RapidMeta
  `P0-denominator-logic`) into standing regression fixtures. **Cap promotion rate; dedup by class**
  (fixture-bloat risk).
- **T9 explicit handoffs/guardrails** — `session_manager.dispatch()` / `core/orchestrator.py`.
  **Design/prototype only** on a non-critical runner path; touches the core loop.
- **T10 DAG-scheduler (SGH)** — **concept-adoption only, evidence-light** (position paper, no empirical
  results — never cite its predicted gains as fact). Promote `cluster/delta_skip.py`'s
  `ContractImpactGraph` to explicit dependency edges **behind a flag, shadow-compared for identical
  verdicts**; `any_of` cross-vendor verdict racing. **Do NOT** rip out the working loop.

---

## Step 6 (north-star) — Benchmark the harness as a constrained-budget closed loop (MADE-derived) = the T-HE Evaluator

> **This step *is* the Evaluator of the harness-evolution meta-loop (T-HE, see Framing).** MADE
> supplies the closed-loop, constrained-budget, ablation-based benchmark structure; Niklaus's
> promotion rule (`efficacy + 0.5·all_pass − 0.005·tokens_per_million`, decided on **held-out** data,
> **one mechanism per iteration**) supplies the accept/reject contract on top of it.


**Source (verified 2026-07-04 by fetching abstract + HTML):** Malik, Gal et al., **MADE: Benchmark
Environments for Closed-Loop Materials Discovery**, arXiv 2601.20996
(https://arxiv.org/abs/2601.20996 , HTML https://arxiv.org/html/2601.20996v1 ).
**Truth-first: this is a materials-discovery benchmark, not a methods/LLM-orchestration result — it
is a transferable *design analogy*, not evidence about our harness.** We adopt its evaluation
*structure*, and we do **not** claim any of its numbers apply to us.

**What MADE actually does (verified specifics, quoted terms):** it evaluates agentic pipelines as
**closed-loop campaigns under a constrained oracle budget** (`B ∈ ℕ`; the paper runs an "oracle query
budget of 50" per episode × "5 independent discovery episodes"). Agents are **composed from
interchangeable components** — its four categories are **Planner / Generator / Filter / Selector** —
and it does **component ablation** to isolate each part's contribution. It scores both **efficacy**
and **efficiency** against a baseline: independent metrics **mSUN** ("fraction of (meta)stable,
unique and novel materials proposed") and **AUDC** (Area Under the Discovery Curve), plus
baseline-relative **AF (Acceleration Factor)** and **EF (Enhancement Factor)** measured against a
**random-generator baseline policy**. Reported ablation headline: "Chemeleon + MLIP pipeline achieves
the highest AF among non-agentic methods (**AF = 6.4**)" vs. random baseline (**AF = 1.0**).

**Why it's the right north-star for our cluster harness:** our harness is a truth-gated,
heterogeneous-vendor reproduction loop. MADE's frame maps onto it almost 1:1 — and crucially it says
*measure efficacy AND efficiency vs a baseline under a fixed budget*, which is exactly the gap the
research doc's §1.5 scorecard flags ("nothing is measured") and what T3 + T12b start to close. This
turns "is +Codex-checker worth it?" from an opinion into an ablation number.

**Mapping MADE → our harness benchmark:**

| MADE construct | Our analog |
|---|---|
| Oracle query budget `B` (50/episode) | **Token / cost budget per campaign** (ties to T12b cost-per-accepted-change; the "oracle" = a paid judge/witness call) |
| Closed-loop campaign, 5 episodes | A fixed set of reproduction/verification tasks run N times for variance |
| Composable components (Planner/Generator/Filter/Selector) | **Composable maker/checker/verifier**: writer runner · Codex-checker (T11) · agy-checker · objective witness (T12a) |
| Component ablation | **Ablation arms:** Claude-only baseline · **+Codex-checker** · **+agy** · full quorum |
| Efficacy metric (mSUN, AUDC) | **Accuracy / cross-vendor agreement / caught-bug rate** on the held-out evals (reuse `intelligence/eval_harness.py`; e.g. does the arm catch RapidMeta `P0-denominator-logic`) |
| Efficiency metric (AF, EF vs random baseline) | **Cost-per-accepted-change** and **caught-bugs-per-1k-tokens** vs the **single-agent (Claude-only) baseline** — the direct analog of AF/EF |
| Random-generator baseline | **Single-agent, no-cross-vendor-checker baseline** |

**First step (smallest safe change — design + a shadow harness, zero ship-path impact):** define the
benchmark on paper (task set, budget definition, the four ablation arms, the two metric families) and
implement it as a **shadow eval** on top of the existing `intelligence/eval_harness.py` and the T3
cost metrics — it scores arms **offline against held-out evals** and never touches a ship verdict.

**Files / components:** `intelligence/eval_harness.py` (task set + efficacy scoring), T3
`verdict_trace.py` / T12b cost emission (efficiency scoring), the T11 lane and quorum config (the
ablation arms). All read-only against shipped code.

**Objective gate that proves it works:** the harness produces, for one fixed task set under one fixed
budget, a table with an **efficacy** column and an **efficiency (cost-per-accepted)** column for each
arm (Claude-only / +Codex / +agy / full), with the single-agent arm as the explicit baseline —
i.e. we can finally answer "does +Codex-checker beat Claude-only, and at what cost?" with a number.

**Rollback:** it is an offline shadow eval; delete it and nothing in the ship path changes.

**Done-check:**
- [ ] Budget, task set, and the four ablation arms are written down before any run.
- [ ] One benchmark run yields efficacy + cost-per-accepted per arm vs the single-agent baseline.
- [ ] The report explicitly labels this a **materials-domain design analogy**, not a methods result,
      and cites arXiv 2601.20996.

**Ordering / risk:** depends on **T3 + T12b** (efficiency signal) and benefits from **T11** (the arm
that makes the ablation interesting). **Needs validation** (it's a measurement design, and the metric
choices must be sanity-checked on our small evals). North-star, not a cycle-1 item — but it is the
thing that makes every "is this worth it?" decision downstream *measured* rather than asserted.

---

## Grounding — every mechanism mapped to a real Claude Code primitive (the toolbox our harness runs on)

**Source (verified 2026-07-04 by fetching the doc pages):** the Claude Code docs, https://code.claude.com/docs .
This section turns the harness-evolution framing (TRINITY router + Loop-Library templates + MADE
benchmark + scheduler graph) into a **build plan expressed in features we actually have.** Every
primitive below was read off the live docs; exact pages are in Appendix C. **Truth-first:** where our
runtime is Python/subprocess (Overmind's judges, the SSH cluster) rather than the `claude` CLI, I say
so — those T-items are *analogs* of the CC primitive, not literally the CC feature.

| Our building block | Concrete Claude Code primitive (verified) | Doc |
|---|---|---|
| **Maker/checker split** (T11, T-CV) — implementer ≠ reviewer, different vendor | **Subagents** in `.claude/agents/*.md` (or `~/.claude/agents/`), YAML frontmatter fields `name, description, tools, disallowedTools, model, permissionMode, mcpServers, hooks, maxTurns, skills, effort, isolation`. A dedicated reviewer subagent with `tools: Read, Grep, Glob` + a **`Bash(codex exec *)`** allowance is the different-vendor checker; per-subagent `model`/`effort` restricts and isolates it. | [sub-agents](https://code.claude.com/docs/en/sub-agents) |
| **Objective-gate enforcement** (T12a) — test/build/`node --check`/diff must pass before ship | **Hooks** on blocking lifecycle events: a **`Stop`** hook (fires when Claude finishes; **can block via exit 2 / `decision:"block"`**) or **`PostToolBatch`** hook that runs `npm test` / the suite and blocks on non-zero exit. The docs give this **exact** test-suite-blocker example. | [hooks](https://code.claude.com/docs/en/hooks) |
| **Anti-drift AGENTS.md reread** (T12e) | A **`SessionStart`** or **`UserPromptSubmit`** hook returning **`additionalContext`** (both documented to inject context each turn/run). | [hooks](https://code.claude.com/docs/en/hooks) |
| **Different-vendor check as a gate** (T-CV) | Either a **`SubagentStop`** hook (blocks when the reviewer subagent finishes) **or** an **`agent`-type hook** (`type:"agent"` spawns a verifier subagent) **or** a **`mcp_tool`-type hook** — all documented hook handler types. The checker itself shells to `codex exec` via a `Bash`-tool allowance. | [hooks](https://code.claude.com/docs/en/hooks) |
| **Cost-per-accepted-change** (T12b) | **Headless `claude -p --output-format json`** returns **`total_cost_usd` and a per-model cost breakdown** per invocation — the exact number T12b needs, no estimation. | [headless](https://code.claude.com/docs/en/headless) |
| **Automation / heartbeat + cross-vendor invocation** (T11, T-CV, the loops) | **Headless mode** (`claude -p`, `--bare` for reproducible CI), pipe pattern `git diff main \| claude -p "…linter…"`, `--allowedTools`, `--permission-mode dontAsk` (locked-down CI), `--json-schema` for structured verdicts, `--continue/--resume`. The Agent SDK (Python/TS) is the programmatic form. | [headless](https://code.claude.com/docs/en/headless) |
| **Loop-Library templates as repeatable, gated loops** (T-LL) | **Skills / slash commands**: `.claude/skills/<name>/SKILL.md` or `.claude/commands/<name>.md` → `/name`; frontmatter `allowed-tools, disallowed-tools, argument-hint, disable-model-invocation, context: fork, agent`. **`disable-model-invocation: true`** = a manually-triggered loop; **`context: fork`** runs it in a subagent. Each lane spec (Step 1.6) becomes one skill with its objective gate + stop baked in. | [skills](https://code.claude.com/docs/en/skills) |
| **Loop TRIGGER + goal-condition STOP** (T-LL `/loop` specs, Step 1.6) | **`/loop [interval] [prompt]`** (bundled skill; self-paces if interval omitted; reads `.claude/loop.md`), **`/goal [condition]`** (works across turns until a verifiable condition is met), **`/schedule`** (cloud routines), **`/compact`** (free context before long runs), **`/effort [high\|xhigh]`**. All verified real. | [commands](https://code.claude.com/docs/en/commands) · [goal](https://code.claude.com/docs/en/goal) |
| **Connectors (act-not-suggest) + tool wiring the evolution loop mutates** (T12f, T-HE) | **MCP** via `.mcp.json` / `claude mcp add` (scopes local/project/user); servers **read *and* act** (create PRs, query DBs, push events); tools named **`mcp__server__tool`**, permission-scopable, callable from **hooks** (`type:"mcp_tool"`) and **headless** (`--mcp-config`). This is the write-back loop the research doc's §1.5 "connectors" row says we lack. | [mcp](https://code.claude.com/docs/en/mcp) |
| **Cheap-router / conductor seat** (TRINITY cost lever) | **Per-subagent `model` + `effort`** frontmatter (docs explicitly: "control costs by routing to faster, cheaper models like Haiku"). A routing subagent on a small model with restricted tools = the Trinity 0.6B-coordinator analog. | [sub-agents](https://code.claude.com/docs/en/sub-agents) |
| **Subprocess watchdog / hard stop** (T1, T12c) | *Analog, not the CC feature:* headless documents a bounded background-subagent wait (`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS`, default 10 min) and `system/api_retry` events — the same *shape* as T1's timeout+retry, but Overmind's judges/SSH run via Python subprocess, so T1 stays our own `subprocess_utils.py` watchdog. | [headless](https://code.claude.com/docs/en/headless) |
| **Structured/typed handoffs + guardrails** (T9) | **Hooks** as guardrails (`PreToolUse` deny / `PostToolUse` block) + **subagents** as typed handoff boundaries with their own tool/permission scope. Maps T9's OpenAI-SDK primitives onto CC-native ones. | [hooks](https://code.claude.com/docs/en/hooks) · [sub-agents](https://code.claude.com/docs/en/sub-agents) |

**Net:** the two top moves and the cross-vendor gate are **buildable today with documented CC features**
— T12a objective gate = a blocking `Stop`/`PostToolBatch` hook running the suite; T-CV/T11
different-vendor check = a reviewer subagent (or `agent`/`mcp_tool` hook) that shells to `codex exec`;
T12b cost = `claude -p --output-format json`'s `total_cost_usd`; T-LL loops = skills/slash commands
with `disable-model-invocation`; the cheap router = a small-`model` subagent. Overmind's Python
substrate keeps its own watchdog (T1) and verdict logic; the CC primitives are how the *harness around*
each model is wired and evolved.

---

## Appendix A — Adopt-today vs needs-validation (quick reference)

| ID | Move | Tier | Flag | First-step surface |
|---|---|---|---|---|
| T-HE (discipline) | Harness-evolution accept/reject rule (blended score, held-out, 1 mechanism) | adopt-today ★ | (process rule) | eval_harness + T3/T12b metrics |
| T-HE (automation) | Autonomous Proposer rewriting harness config | north-star | gated on Step 6 | eval_harness + flag-gating |
| Step 0 | Portable paths | adopt-today | (refactor) | `nightly/runner.py` |
| T3 | Tracing on | adopt-today | tracer no-op default | `verdict_trace.py`, `orchestrator.py` |
| T12b | Cost-per-accepted | adopt-today | additive metric | via T3 |
| **T12a** | **Objective-gate audit (WARN)** | **adopt-today ★** | `OVERMIND_OBJECTIVE_GATE_AUDIT=shadow` | `orchestrator.py:775-819` |
| T12e | AGENTS.md reread | adopt-today | additive hook | loop entrypoints |
| T-LL | Loop-Library lane specs (objective+proof+stop) | adopt-today | (specs only) | SKILL.md loop specs |
| **T-LFD** | **Loss-function design + anti-reward-hacking fences per loop** | **adopt-today ★** | (specs only) | loop specs + `verification/` instruments + T3/T12b |
| **T-CV** | **Cross-vendor check-before-ship gate (mandatory habit)** | **adopt-today ★** (once T11 live) | `OVERMIND_REQUIRE_CROSS_VENDOR_CHECK` | `nightly/runner.py`, `judge_factory.py`, `multi_persona.py` |
| **T11** | **Codex-checker lane** | **adopt-today ★** | `OVERMIND_CODEX_BUGHUNT_LANE`, `effort` | `judge_backends.py`, `multi_persona.py` |
| T12f | Shared signal store (read-only) | adopt-today | read-only phase | Sentinel↔Overmind JSONL |
| T12f-tool | **MemClaw** mirror-only shadow (file state = floor) | adopt-today (mirror) / validate (promote) | mirror writer + MCP | new service + `.mcp.json` |
| Step 4.6 | **Vault** (Obsidian-compatible markdown KB, human layer) | adopt-today | (local folder) | `F:\overmind\vault\` + skills/`Stop` hook |
| T12g | Build-order governance | adopt-today | (policy) | gate on scheduling cluster branch |
| T1 | Subprocess watchdog | validate (shadow→enforce) | `OVERMIND_SUBPROC_WATCHDOG` | `subprocess_utils.py` |
| T2 | Sentinel rule watchdog | validate (shadow→enforce) | `SENTINEL_RULE_TIMEOUT_MS` | Sentinel `scan.py` |
| T5 | Auth preflight | validate (shadow) | flag | `judge_factory.py`, `transport.py` |
| T6 | Node breaker/backoff | validate (fixture) | flag | `cluster/scheduler.py` |
| T4 | Durable journal | validate (crash test) | journal-only | `cluster/registry.py` |
| T10-esc | Escalation ceiling | validate | (rides T1/T6) | scheduler retry path |
| T7 | Credibility/debate judge | validate (evals) | shadow | `llm_judge.py` |
| T8 | Failure→regression loop | validate | capped promotion | `failure_taxonomy.py` |
| T9 | Explicit handoffs | validate (design-only) | prototype path | `orchestrator.py` |
| T10-DAG | DAG scheduler | validate (concept-only) | flag, shadow | `cluster/delta_skip.py` |
| MADE | Harness closed-loop benchmark (efficacy+efficiency, ablation) | validate (north-star) | offline shadow eval | `intelligence/eval_harness.py` + T3/T12b |

## Appendix B — Universal rollback contract
Every change is behind an env flag with the prior code path left intact for **one full nightly cycle**
before the old path is removed. No verdict changes silently. An audit that tightens ship criteria
(T12a) ships as WARN for a full cycle before it can block, and even then reuses the existing
`UNVERIFIED` verdict rather than flipping a PASS.

---

## Appendix C — External sources cited in this checklist (verified 2026-07-04)
- **Research doc (source of record):** `2026-07-04-cutting-edge-improvements.md` (this folder) — carries
  its own full source list (Anthropic multi-agent, OTel, Diagrid/DBOS, the arXiv set incl. the
  scheduler-graph paper arXiv 2604.11378 used as the T10/SGH execution-graph layer, Boris Cherny
  Loop Engineering, etc.).
- **★ Joel Niklaus — "Don't Train the Model, Evolve the Harness"** (Hugging Face, July 2026), the
  **centerpiece framing**: https://huggingface.co/spaces/joelniklaus/harness-optimization (app:
  https://joelniklaus-harness-optimization.hf.space/ ). Verified by rendering the app: DeepSeek-V4-Pro
  0% → 5.0% all-pass / 80.1% criterion on LAB with zero weight changes; Proposer (Claude Opus 4.8, one
  mechanism/iteration) + Evaluator (24-task dev × 3 trials, promote if ≥1 pt on blended score
  `pooled_criterion_rate + 0.5·all_pass_rate − 0.005·tokens_per_million`); "never read the test split";
  "5 of top 6 harnesses are deterministic code, not prompt edits"; robustness transfers / prompt
  playbooks backfire across model families; ~$120–160 per 100-task run. **Not fully verified (flagged):**
  the related **Meta-Harness** reference impl (https://yoonholee.com/meta-harness/ ,
  https://github.com/stanford-iris-lab/meta-harness) surfaced via search but not fetched by me; and the
  search-summary "Sonnet-4.6 performance at 7× cost" claim is **omitted as unverified**.
- **★ TRINITY: An Evolved LLM Coordinator** (Xu et al., Sakana AI, ICLR 2026) — empirical validation of
  the conductor + maker/checker architecture: https://arxiv.org/abs/2512.04695 (HTML
  https://arxiv.org/html/2512.04695v3 ; https://sakana.ai/trinity/ ). **Verified by fetching the paper:**
  0.6B coordinator (+10K head, <20K learnable params) assigning Thinker/Worker/Verifier per turn; new
  SOTA 86.2±0.5% on LiveCodeBench beating GPT-5 (0.838) / Gemini 2.5-Pro (0.672) / Claude-4-Sonnet
  (0.465); acceptance-driven termination (loop until Verifier ACCEPTs); zero-shot transfer to
  AIME/BigCodeBench/MT-Bench/GPQA. **Reported-not-verified (explicitly flagged in-text):** "a top-tier
  model as coordinator performs worse" (paper never varies coordinator size — ablations are
  component-only) and "verifier must be a different model" (paper does not mandate Worker≠Verifier).
  The different-vendor-check principle is retained as **our own** `enforce_distinct_families` /
  reviewer≠writer rule, reinforced by — not derived from — TRINITY. Related orchestration systems noted
  in passing (not load-bearing, not fetched): Sakana **Fugu**, Microsoft **Terminus-4B**.
- **★ Elvis Sun — Loss-Function Development (LFD) + `/lfd-design` skill:**
  https://github.com/elvisun/loss-function-development (verified 2026-07-04: public repo, **155★ / 9
  forks**; `/lfd-design` *"designs loss functions for long-running autonomous agent loops"*). Verified
  content: 4-part loss (target/constraints/instruments/forced-entropy); reward-hacking quote *"every
  cheap path you don't fence off is a direction it will sprint down… memorize your eval, mine your
  miss-lists into lookup tables, and game your judge"*; the skill red-teams its own drafts and keeps a
  *"cheat museum."* Relays Peter Steinberger's *"design loops that prompt your agents."* **Reported-not-
  verified (flagged):** the *"50× / 30 hours / $40"* and *"agent cheated 3×"* figures are **Elvis Sun's
  own anecdotes**, NOT found in the repo README — cited as anecdotes, never as measured constants.
- **Caura MemClaw** — governed shared memory (Apache-2.0), the concrete tool for the shared-signal store
  (Step 4.5): https://github.com/caura-ai/caura-memclaw , https://memclaw.net/ . Verified README features:
  MCP-native (`/mcp`), visibility scopes (`scope_agent`/`scope_team`), 4 trust tiers, keystone policies,
  full audit log, tenant isolation (row-level), contradiction detection, auto knowledge graph,
  self-improving retrieval; Docker Compose or Python+PostgreSQL deploy. **Verified-as-a-README-claim
  (not independently measured):** eToro 300+ agents / 26,500+ memories / 1,372 shared skills / 23 ms p50.
  Adopted **shadow-first (mirror-only), file state as the floor** — see Step 4.5.
- **AI Edge (@aiedge_) — beginner's Loop Engineering guide** (references Boris Cherny's loop pattern +
  Fable 5), used in Step 1.6 for the **6-part loop anatomy** and the copy-pasteable `/loop` template.
  Practitioner guide; its command claims were **verified against the Claude Code commands reference**
  before restating: `/loop`, `/goal`, `/schedule`, `/compact`, `/effort` are all real (see
  https://code.claude.com/docs/en/commands and https://code.claude.com/docs/en/goal ). **Flagged
  reported-not-verified:** the "`/goal` runs a separate fast grader model each turn" detail is the
  guide's framing (docs confirm work-until-condition, not the separate-grader mechanism).
- **Matt Pocock — skills** (curated Claude Code skills), starting patterns for the loop templates
  (Step 1.6): https://github.com/mattpocock/skills . Verified skills cited: `tdd`, `diagnosing-bugs`,
  `code-review`, `to-prd`, `grill-with-docs`, `triage`, `improve-codebase-architecture` (names +
  descriptions quoted from the repo; internal implementation not audited — adapt, don't drop in).
- **sanyuan0704/sanyuan-skills** (MIT, ~3.7k★), production-grade skills + meta-tooling to author ours
  (Step 1.6): https://github.com/sanyuan0704/sanyuan-skills . Verified skills: **Code Review Expert**
  (SOLID/security/perf/error-handling → checker gate), **Skill Forge** (meta-skill, "12 techniques" →
  author our lane skills), **Skill Review** (audit structure/token-efficiency/anti-patterns → audit
  them), **Wiki Ingest** (compile notes → vault/KB), plus Sigma / Book Study (learning). **Security
  caveat:** third-party skills run instructions in the agent — **audit contents before install**, don't
  trust-on-faith (matches the Sentinel plugin-loader / arbitrary-code-at-push-time warning).
- **Vault / Fable×Obsidian tip** (practitioner) — basis for the Step 4.6 markdown-vault knowledge store.
  **Truth-first:** the "Fable is the world's best at long tasks" line is **unverified marketing** — not
  repeated as fact; the local-markdown-vault design stands independently.
- **★ Claude Code documentation** — https://code.claude.com/docs — the **real toolbox** every mechanism
  is grounded in (see the *Grounding* section). Pages fetched & verified 2026-07-04:
  **subagents** (https://code.claude.com/docs/en/sub-agents — `.claude/agents/*.md`, frontmatter
  `name/description/tools/disallowedTools/model/effort/permissionMode/isolation/…`, per-subagent model
  for cost routing); **hooks** (https://code.claude.com/docs/en/hooks — 31 lifecycle events;
  blocking `Stop`/`PostToolBatch`/`PreToolUse`/`SubagentStop`; handler types command/http/mcp_tool/
  prompt/agent; documented `npm test` test-suite-blocker example; `additionalContext` injection);
  **headless** (https://code.claude.com/docs/en/headless — `claude -p`, `--output-format json` with
  `total_cost_usd` + per-model cost breakdown, `--json-schema`, `--allowedTools`, `--permission-mode`,
  `--bare`, `--continue/--resume`, Agent SDK); **skills/commands** (https://code.claude.com/docs/en/skills
  — `.claude/skills/<name>/SKILL.md` & `.claude/commands/<name>.md` → `/name`, frontmatter
  `allowed-tools/disallowed-tools/argument-hint/disable-model-invocation/context:fork/agent`);
  **MCP** (https://code.claude.com/docs/en/mcp — `.mcp.json`/`claude mcp add`, read-and-act connectors,
  `mcp__server__tool` naming, callable from hooks and headless). **Truth-first:** Overmind's judges and
  the SSH cluster run on a Python/subprocess substrate, so T1's watchdog and the verdict logic are our
  own code — the CC primitives are the documented model for the *harness wiring* (checker subagents,
  gate hooks, cost readout, loop skills, connectors), and that mapping is labeled analog-not-literal
  where it is one.
- **Forward Future — Loop Library:** https://signals.forwardfuture.com/loop-library/ — used in
  Step 1.6 (T-LL). Template names and stop conditions were read off the live page on 2026-07-04
  (Multi-LLM convergence, Clodex adversarial-review, Quality streak, Production error sweep,
  Research-to-artifact, Post-release baseline / recovery proof). Quoted stop conditions are verbatim.
- **arXiv 2601.20996 — MADE: Benchmark Environments for Closed-Loop Materials Discovery**
  (Malik, Gal et al.): https://arxiv.org/abs/2601.20996 , HTML https://arxiv.org/html/2601.20996v1 —
  used in Step 6. Verified constructs: constrained oracle budget `B∈ℕ` (50 queries/episode × 5
  episodes); components Planner/Generator/Filter/Selector; metrics mSUN, AUDC, AF, EF vs a
  random-generator baseline; ablation headline AF=6.4 (Chemeleon+MLIP) vs 1.0. **Materials-domain
  design analogy only — not a methods/LLM result; none of its numbers are claimed to apply to us.**

---

*This checklist is planning output only. It cites the research doc
`2026-07-04-cutting-edge-improvements.md` as its source of record (plus the two external sources in
Appendix C) and does not modify Sentinel, Overmind, the harness, or Dispatch. File:line references
were spot-verified against the working tree of `F:\overmind\overmind` on 2026-07-04; verify any
unspot-checked line with `grep` before editing. External claims were verified by fetching the live
pages before assertion; where a source's page did not state a specific number, that gap is noted
rather than filled.*
