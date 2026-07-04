# WORLD_CLASS_SPEC — Best-in-the-world, *for its purpose*

**Date:** 2026-07-04
**Status:** SPEC / north-star contract. Design document. No production behavior is defined-in
by this file; it is the yardstick that the harness-evolution loop and the roadmap
(`ROADMAP.md`) are measured against.
**Owner:** Mahmood Ahmad
**Source of record:** `F:\overmind\workflow-upgrade\2026-07-04-cutting-edge-improvements.md` (research),
`…-implementation-checklist.md` (grounded plan), `F:\overmind\vault\` (consolidated knowledge),
project memory north-star.

---

## 0. The purpose (anchor — do not drift)

This harness is **not** a general-purpose agent framework. It is a **truth-gated,
heterogeneous-vendor (Claude + 2× Codex + agy) reproduction-and-verification orchestrator**
for **evidence-synthesis methods research** (AdaptShrink, transport-NMA / registry-borrowing,
DTA, dose-response, consensus-or-flag) and the **RapidMeta** app pipeline.

"World-class for its purpose" is a bounded, testable claim: **best-in-the-world at
truth-gated cross-vendor reproduction-and-verification of quantitative evidence-synthesis
work, provably** — not "a good agent framework." Every differentiator below is scoped to that
purpose, and the benchmark in §3 is designed so it *could show us not winning*.

**Defensible edge (the moat):** cross-vendor **consensus-or-flag** verification + **objective
truth-gates** under every accept + a **private eval / ground-truth corpus** (AACT
registered-vs-published, curated gold meta-analysis library, R/metafor parity) that nobody
else can score against. *"The product is a weekend; the eval nobody else can score against is
the moat."*

---

## 0.5 Control model — Dispatch is the single control plane (the conductor)

**Foundational architectural constraint (Mahmood):** the harness is **controlled entirely through
Dispatch.** There is no separate bespoke control daemon; **Dispatch *is* the control plane.**

- **Dispatch is the conductor, not a worker.** It occupies the Trinity "small manager/router" seat:
  it **routes each unit of work to the right VENDOR** (Claude / Codex-A / Codex-B / agy) **on the
  right NODE** (pc1 / laptop / pc2), **gates the result, and moves on** — it does **not** do the
  heavy reasoning itself. This is the pattern already proven in production: the Dispatch orchestrator
  spawns and steers code-task lanes, runs the cross-vendor witness, and the scheduled
  agent-drain-watchdog reports back to Dispatch, which is the "hands" that relaunch/refill.
- **Everything runs through Dispatch primitives.** Drive lanes with **`start_task` / `start_code_task`
  / `send_message`**; observe with **`read_transcript` / `list_sessions`** + the **scheduled
  agent-drain-watchdog**; the watchdog reports to the Dispatch orchestrator which relaunches to keep
  lanes drained-to-cap. No control logic lives outside this loop.
- **Vendor lanes are stateless workers.** All harness *control* logic — routing, cap-detection and
  rerouting, truth-gating, consensus-or-flag adjudication, the drain-to-cap loop, and
  cost-per-accepted-change accounting — is expressed as **Dispatch-orchestrated flows**. The vendor
  seats hold no control state; Dispatch dispatches to them and owns the gate.
- **The router need not be the biggest model** (Trinity, verified: a 0.6B coordinator beats a frontier
  pool). This applies **only to the Dispatch conductor seat** (pure routing / low reasoning) and is a
  **tested cost lever, not an assumption** — see §1.5. All *methods / reproduction / verification* work
  runs on frontier models.

This constraint is load-bearing for the differentiators below: D1 (consensus-or-flag), D2
(objective-gate floor), D4 (provenance), and D5 (cost-per-accepted) are **defined as Dispatch flows**,
and D7 makes the control plane itself a differentiator.

---

## 1. The seven differentiators (what makes it best-in-class FOR THIS PURPOSE)

Each differentiator states: **the claim**, **why it is defensible for this purpose**, and **the
objective signal that proves it holds** (so none is a vibe).

### D1 — Cross-vendor consensus-or-flag as a first-class primitive
- **Claim:** Every ship-eligible verdict on a methods artifact is produced by ≥2 **independent
  model families** (Anthropic / OpenAI / Google), and disagreement **flags** rather than silently
  resolving to the optimistic side. Homogeneous agreement is explicitly *not* counted as
  independent corroboration.
- **Why defensible:** Correlated judges share failure modes ("Nine Judges, Two Effective Votes",
  arXiv:2605.29800). A single-vendor stack — however strong — cannot decorrelate its own blind
  spots. Our heterogeneous seats are a structural, not prompt-level, advantage; robustness of this
  kind *transfers across models* (Niklaus), unlike prompt playbooks.
- **Proof signal:** `enforce_distinct_families` holds in 100% of ship verdicts; a
  `cross_vendor_check_present(vendor=…)` field on every verdict; the benchmark's heterogeneous arm
  beats the homogeneous arm on caught-defect rate at equal or lower cost (§3).

### D2 — An objective truth-gate floor under every accept
- **Claim:** No headline/ship decision rests on **judges or consensus agreeing alone**. Under every
  accept there is a **named objective witness** — a test-suite exit code, `node --check`, a build,
  a Playwright runtime check, a byte/numeric diff, numerical-continuity, or R/metafor parity — or
  the task is explicitly reclassified **human-in-the-chair** (not loop-eligible).
- **Why defensible:** This is the load-bearing Loop-Engineering rule ("VERIFY = an objective gate,
  not a second agent agreeing"). It is what makes "consensus-or-flag" *sound*: consensus is only as
  strong as the objective witness beneath it. It directly fences the reward-hack where two optimists
  agree on a wrong answer.
- **Proof signal:** the objective-gate audit reports **0 ships resting on consensus-without-a-floor**
  once promoted (starts as a measured WARN count; §2 increment 1).

### D3 — Reproduction-or-flag discipline (independent re-derivation, not review)
- **Claim:** A quantitative result is accepted only when an **independent vendor reproduces the
  number to declared precision** (byte/numeric parity), or the divergence is flagged. Verification
  is *re-derivation*, not "a reviewer read it and it looked right." (Proven today: triple-vendor
  witness reproduced transport-NMA to full precision; Codex/agy bug-hunts found real defects.)
- **Why defensible:** For methods research the failure mode is a *silently wrong number*, not a
  crash. Only independent reproduction catches it. This is the exact shape of our private-corpus
  moat: AACT registered-vs-published and gold-MA parity are reproduction targets, not opinion targets.
- **Proof signal:** every accepted quantitative claim carries ≥1 independent-reproduction witness id;
  the benchmark measures caught planted-numeric-defects (e.g. RapidMeta `cE>cN`).
- **Promotion bar (AN-5, DFAH arXiv:2601.15322):** a result is promoted to "verified" only on **passk
  (all-k-succeed across N replays)**, not pass@k (any-of-k); plus an optional **signature-determinism**
  witness (identical tool-call+args across replays) — `verification/passk_witness.py`. Honest caveat:
  determinism proves *auditability*, not *correctness* (a deterministically wrong answer is still wrong),
  so it pairs with the reproduction/correctness gate, never substitutes.

### D4 — Full auditability / provenance of every claim
- **Claim:** Every verdict is reconstructable end-to-end: which witnesses ran, which vendor produced
  what, span-level timing/tokens, the signed cert bundle, and the JSONL finding stream — with
  freshness/replay protection so a stale pass cannot be re-presented as current.
- **Why defensible:** A methods claim you cannot audit is not a methods claim. Provenance is what
  lets a reviewer (or a future session) trust an accept without re-running it, and is a precondition
  for the private-corpus moat to compound (T8 failure→regression).
- **Proof signal:** span coverage = 1.0 over the expected pipeline stages on a traced verdict; signed
  bundle verifies; `UNVERIFIED` is emitted (never a silent pass) when a witness SKIPs on a missing
  baseline.

### D5 — Cost-per-accepted-change economics made visible (and fenced)
- **Claim:** The harness measures **cost-per-accepted-change** and **acceptance rate** per loop from
  real spend (`claude -p --output-format json` `total_cost_usd` + Codex/agy usage), surfaces loops
  below the practitioner ~50% break-even (labelled a heuristic, not a measured constant), and enforces
  a hard money/wall-clock ceiling.
- **Why defensible:** A truth-gated harness that is 10× the cost of a single agent for the same
  accepted output is not world-class *for a working research program* — it is a science project.
  Efficiency is half the win condition in §3, on purpose. Making spend visible also fences the
  "burn tokens to look busy" reward-hack.
- **Proof signal:** a cost-per-accepted-change number exists per loop for one nightly; the benchmark
  scores efficiency as a first-class axis, not a footnote.

### D6 — A private eval / ground-truth moat that grows with use
- **Claim:** Superiority is scored against a **private, curated, truth-gated corpus** — AACT
  registered-vs-published, the gold meta-analysis library, R/metafor parity fixtures — that is
  **blinded to the agent at run time** (never readable mid-run) and **grows** as production failures
  are auto-promoted into regression fixtures (T8).
- **Why defensible:** Anyone can clone a dashboard generator in a weekend; nobody else can score
  against our corpus. The moat is the eval, and it compounds: every caught failure becomes permanent
  coverage. This is the strategic asset the whole program protects.
- **Proof signal:** the benchmark in §3 runs *on this corpus*; the held-out split is never read during
  a run; fixture count grows monotonically as failures are classified.
- **Adversarial audit before promotion (AN-7, BenchJack arXiv:2605.12673):** an in-house adversarial
  audit (`benchmark/benchjack_audit.py`, a *method* not a dependency) red-teams the private corpus for
  ways to score without solving — id-leak, keyword-shortcut, template-uniformity, missing-canary — and
  runs before any evolution cycle promotes a candidate. Discovered exploits become **negative-memory
  regression fixtures** (grows the moat). Run on the current corpus it already surfaces 10 real
  weaknesses (the keyword-shortcut / template-uniformity risks `BENCHMARK_RESULTS.md` flagged as open) —
  turning "still open" limitations into tracked fixtures, honestly.

### D7 — Dispatch as the single control plane (the conductor)
- **Claim:** All control is exercised through **one** plane — Dispatch — which routes each unit of work
  to the strongest live vendor on the right node, gates the result against the objective-gate floor
  (D2) before accepting any lane's "pass", reroutes on vendor-cap detection, and records provenance
  (D4) of every claim through the flow. There is no second control path.
- **Why defensible:** A single, uniform control plane is what makes the other six *auditable and
  evolvable*: every accept, reroute, and cost event passes through one instrumented conductor, so the
  whole system is one A/B-testable loop (Niklaus evolve-the-harness) rather than a tangle of bespoke
  daemons. It is also the Trinity-validated shape — a light conductor routing a frontier pool beats any
  single model — and it means the control logic itself can be improved without touching the vendor
  workers.
- **Proof signal:** every ship verdict carries a Dispatch provenance record (vendor, node, gate
  outcome, cost); a vendor-cap event produces a recorded reroute to a non-capped vendor with no lost
  work; no "pass" is accepted by Dispatch without a named objective witness under it (D2).

**Why exactly these seven:** D1–D3 are the *correctness* core (independent, gated, reproduced);
D4 is the *trust* layer (auditable); D5 is the *economics* that keep it usable; D6 is the *moat*
that makes the whole thing defensible and measurable; **D7 is the *control plane* that binds the other
six into one instrumented, evolvable conductor.** Drop any one and the claim "best-in-the-world for its
purpose" stops being provable.

---

## 1.5 Vendor panel / model selection — FRONTIER-heterogeneity, qualified on the HARDEST tasks

**Principle (Mahmood, empirical):** the cross-vendor panel must be **heterogeneity across FRONTIER
models.** Weaker/cheaper models are **excluded from reasoning / reproduction / verification seats.**
This is not cost-indifference — it is that, for this work, a weak model in a verification seat adds
*correlated, obvious* failures (little independent signal) and can *rubber-stamp* a wrong number, which
is worse than no panel member at all.

### 1.5.1 The capability-cliff evaluation principle (the load-bearing rule)
Mahmood's observed failure mode: **weaker models — including GLM/Chinese open models (Qwen / DeepSeek /
Kimi / GLM class) and lower-tier models — often perform *well on moderate tasks* but *collapse on
really complex, sophisticated, long-horizon* code/reasoning.** The cliff is **invisible on easy tasks**.
Therefore:

1. **A model's fitness for a seat MUST be judged on our HARDEST tasks, never on easy/average ones.**
   Demo/benchmark performance on standard suites is **not sufficient** — the cliff won't show there.
   The panel-qualification eval stresses each candidate on the **most complex methods/reproduction
   tasks**: multi-arm NMA parity, DTA bivariate convergence, the borrowing-field k-fold, and long
   agentic bug-hunts. A candidate qualifies for a seat only if it holds accuracy **there**.
2. **Frontier-heterogeneity matters because frontier models from different vendors fail
   *differently*** — independent, subtle failures → genuine error-catching when they disagree. Weak
   models fail in **correlated / obvious** ways → little independent signal. This is *why* the panel
   must be frontier-only: decorrelation is only valuable between models that are each individually
   above the cliff.
3. **"Always try to be groundbreaking" = push frontier models hard on the hardest tasks; do not dilute
   the panel with weak models to save cost.**

### 1.5.2 Per-seat model selection (recommendations are TESTED, not assumed)
Truth-first: recommend a model per seat only **after** (or with a concrete plan to) empirically
qualify it on our hardest tasks per §1.5.1. Current best-available anchors:

| Seat | Role | Model policy | Evaluation to run |
|---|---|---|---|
| **Claude (worker + verifier)** | reasoning / method dev / verification | **top-tier (Opus-class)** for work | **Test Sonnet-top vs Opus for the *verifier* role** — Sonnet may be a fine cheaper cross-check **IF it holds accuracy on our hardest tasks**; qualify on the cliff, don't assume. Sonnet-top is **the one cheaper candidate genuinely worth testing** as verifier/worker. Weak = out. |
| **GPT via Codex (worker + verifier)** | strongest bug-finder / cross-vendor check | **strongest Codex/GPT available (today gpt-5.5 on both seats)** | evaluate newer GPT frontier models as they land; never drop below frontier for verification. |
| **Gemini via agy / Antigravity (worker + verifier)** | Google-family decorrelation seat | **strongest Gemini frontier model** | evaluate Gemini frontier alternatives; qualify on hard tasks. |
| **Dispatch conductor (routing only)** | route/gate/move-on, low reasoning | **frontier by default;** a cheaper model is acceptable **only here** (Trinity: router needn't be biggest) | **tested option, gated on not hurting outcomes** — measure that routing quality and end-to-end outcomes do not regress before adopting a cheaper conductor. NOT an assumption. |

**Reconciliation with Trinity:** the "router needn't be the biggest model" result applies **only to the
narrow Dispatch routing seat** (pure routing decisions). Every actual methods / reproduction /
verification unit runs on a **frontier** model. A cheaper conductor is a *tested* cost lever, never a
default.

### 1.5.2b D1 decorrelation sub-gate — consensus is MEASURED, not assumed (AN-3)
"Different vendor ⇒ independent" is an *assumption*; correlation is structural and can span families
("artificial hivemind", arXiv:2605.29800). So D1 now **measures** effective independence: per verdict,
compute a **Kish/design-effect `n_eff`** over the *agreeing* judges (`judge_factory.kish_neff` /
`decorrelation_gate`, recorded on the provenance line as `consensus_neff` / `consensus_counts`). If
`n_eff < 2.0` (or fewer than two distinct families agreed), the agreement does **not** count as
consensus — the harness falls through to the D2 objective witness or abstains, never treating a
correlated "agreement" as corroboration. Three same-family judges ⇒ `n_eff ≈ 1` ⇒ not consensus.

### 1.5.3 Benchmark implication — measure each vendor-model's MARGINAL value
The consensus-or-flag eval (§3) must **measure the marginal verification value of each panel member**:
a vendor-model that mostly errors, or mostly rubber-stamps (agrees without catching planted defects),
**adds no verification value and is dropped from the panel.** Panel membership is *earned* by
**genuinely catching errors / adding independent signal on the hardest tasks**, not granted by vendor
identity. This is the objective test that keeps the panel frontier-only and non-diluted.

---

## 2. What each differentiator requires that we do NOT yet fully have

(Full evidence-based gap analysis lives in `GAP_ANALYSIS.md`; this is the spec-level summary of the
*bar* each differentiator sets.)

| Diff | Bar it sets | Meets today | Gap |
|---|---|---|---|
| D1 | ≥2 independent families on every ship verdict, recorded | family-decorrelation machinery exists (`judge_factory`) | not *recorded as a first-class field*; runtime often 1 live engine (auth) |
| D2 | objective witness under every accept, or human-in-chair | many real witnesses exist | **no floor assertion** — judge-only ships are possible and *uncounted* |
| D3 | independent reproduction per quantitative claim | proven manually (transport-NMA) | not a *standing, per-claim* recorded stage |
| D4 | full span/provenance on every verdict | tracer + signed bundles built | tracer **not threaded through** most callers |
| D5 | cost-per-accepted-change per loop | rough `_run_cost_usd` estimate only | **no real `total_cost_usd` parse; no acceptance-rate** |
| D6 | blinded, growing private corpus as the scorer | corpus + evals exist | benchmark (§3) not yet standing; blinding not enforced as a rule |
| D7 | one Dispatch control plane; gate before accept; reroute on cap; provenance per claim | Dispatch orchestrator + drain-watchdog proven in production | control flows not yet *expressed as recorded Dispatch provenance*; objective-gate floor (D2) not yet enforced at the Dispatch accept point |
| §1.5 | frontier-only panel, each seat's model qualified on the HARDEST tasks; marginal value measured | frontier seats configured (Claude/Codex gpt-5.5/agy) | no *capability-cliff qualification eval*; per-vendor marginal-value not measured; Sonnet-top-as-verifier untested |

---

## 3. THE BENCHMARK that would PROVE superiority

**Name:** MADE-style constrained-budget closed-loop harness benchmark (the "T-HE Evaluator").
**Shape:** a MADE-derived (arXiv:2601.20996) **closed-loop** eval that runs the *same task set*
through three harness configurations under an **identical budget ceiling**, scored on **both
correctness/agreement AND efficiency**, on **our private ground truth** (D6), decided on a
**held-out split the agent never reads** (Niklaus "never read the test split").

### 3.1 The three arms (this is the head-to-head)
1. **A — Single-agent baseline.** One vendor (Claude), one pass, its own self-check. No cross-vendor,
   no consensus. (The "capable model, brittle scaffold" control.)
2. **B — Homogeneous multi-agent baseline.** N agents, **same vendor/family** (e.g. 3× Claude
   maker+checkers). Tests whether *more agents* alone — without vendor diversity — is the win. This
   is the honest control that isolates our D1 claim: if B ≈ our arm, heterogeneity buys nothing.
3. **C — The heterogeneous truth-gated harness (ours).** Cross-vendor consensus-or-flag (D1) +
   objective-gate floor (D2) + reproduction-or-flag (D3), **all expressed as Dispatch-orchestrated
   flows** (D7): Dispatch routes each unit to the strongest live vendor/node, gates against the
   objective floor before accepting any lane's pass, and reroutes on vendor-cap. Under the same budget.

**All three arms run through Dispatch** (the single control plane); the arms differ only in *what
Dispatch orchestrates* (one vendor / N same-vendor / frontier-heterogeneous panel), so the head-to-head
isolates the panel, not the plumbing.

**Panel-qualification pre-gate (per §1.5 — runs before C is even assembled):** each candidate
vendor-model must pass the **capability-cliff qualification** — hold accuracy on the *hardest* subset
(multi-arm NMA parity, DTA bivariate, borrowing-field k-fold, long agentic bug-hunts), not on easy
tasks. A model that fails the cliff is excluded from C's reasoning/verification seats. Sonnet-top is
qualified here specifically as a candidate *verifier* seat (cheaper cross-check) — kept only if it holds
on the hard subset.

### 3.2 The task set (on our corpus — D6)
Drawn from the private corpus, mixing **fix tasks** (a real defect is present — the harness should
catch/repair it) and **regression tasks** (the artifact is correct — the harness must *not* flag it,
i.e. no false alarms). Concrete seeds that already exist on disk:
- RapidMeta `P0-denominator-logic` planted defects (`cE>cN`, events > N) — **fix tasks with a known
  answer key** (a "found-nothing pass" fails the canary).
- transport-NMA / DTA / NMA reproduction targets with R/metafor parity — **numeric-parity tasks**.
- AACT registered-vs-published pairs — **discrepancy-detection tasks**.
- Clean, known-correct artifacts — **regression / no-false-alarm tasks**.

Minimum honest size: enough that **enumeration doesn't pay** and a single failure mode can't dominate
(MADE/Niklaus both flag a ~24-task dev set as a real limitation — treat dev size as a stated caveat,
not a hidden one). Split into **dev (tuning)** and **held-out (decision)**; the held-out answer key is
outside the agent's tool/file surface.

### 3.3 The exact metrics
Per arm, over the held-out split:
- **Correctness / efficacy:**
  - **caught-defect rate** = fraction of fix tasks whose planted defect was detected (and, where
    applicable, correctly repaired to an objective gate).
  - **false-alarm rate** = fraction of regression (correct) tasks the arm wrongly flagged. (Lower is
    better; a harness that flags everything is not "safe", it is useless.)
  - **numeric-parity rate** = fraction of reproduction tasks reproduced to declared precision.
  - **agreement soundness** = fraction of *agreements* that were actually correct (guards the
    "two optimists agree" hack — an agreement on a wrong answer counts against, not for).
- **Per-vendor marginal value (§1.5.3 — the panel-membership test):**
  - **marginal caught-defect** = defects caught *only because* vendor V was on the panel (drop-one
    ablation: remove V, re-score). A member with ~0 marginal catch adds no verification value.
  - **rubber-stamp rate** = fraction of V's agreements that were on *wrong* answers (V agreed but the
    defect was real). High rubber-stamp = negative signal → **V is dropped from the panel.**
  - This directly enforces "frontier-only, non-diluted": panel membership is earned on the hardest
    tasks, not granted by vendor identity.
- **Efficiency:**
  - **cost-per-accepted-change** = total USD spend / number of accepted-and-correct changes
    (from real `total_cost_usd` + Codex/agy usage — D5).
  - **wall-clock per accepted change** and **tokens per accepted change** (secondary).
- **Control-plane integrity (D7):** fraction of accepts that carried a Dispatch provenance record with
  an objective witness under them (target 1.0); reroute-on-cap success (a capped vendor's unit
  completes on a rerouted vendor with no lost work).
- **Blended promotion score** (Niklaus form, adapted, decided on held-out only):
  `score = caught_defect_rate − λ_fa · false_alarm_rate + 0.5 · numeric_parity_rate − 0.005 · cost_per_accepted_usd_normalized`
  where `λ_fa` penalizes false alarms and the cost term is normalized so a cheaper arm at equal
  efficacy wins. (Weights are design parameters to be pinned *before* the run and never tuned on the
  held-out split — pinning them is itself a fence.)

### 3.4 The win condition (stated so it can fail)
Arm **C is "world-class for its purpose"** iff, on the **held-out** split:
1. **C > A** on caught-defect rate **AND** on agreement soundness (heterogeneous truth-gating catches
   defects a single agent misses), **with false-alarm rate no worse than A**; and
2. **C > B** on caught-defect rate **OR** agreement soundness **at equal-or-lower cost-per-accepted**
   (vendor *diversity*, not just agent count, is doing real work); and
3. C's **cost-per-accepted-change is within a pre-declared multiple** of A's (e.g. ≤ Kx — pinned
   before the run), i.e. the truth-gating is affordable, not merely correct.

**Honest failure outcomes this design permits (and must report if they occur):**
- If **B ≈ C**, then heterogeneity is not paying and D1 is *not* a differentiator — report it, and
  either strengthen the reproduction/gate layers or drop the vendor-diversity claim.
- If **C's cost-per-accepted ≫ A's** without a matching efficacy gain, the harness is correct but not
  *world-class for a working program* — report it and attack D5.
- If **C's false-alarm rate is high**, consensus-or-flag is flagging noise — report it; a harness that
  cries wolf is not defensible.

**Truth-first mandate:** the benchmark is built to be honest. No arm's prompts/config may read the
held-out split; weights and the cost multiple K are pinned before running; a "found-nothing pass" on a
fix task is a *failure*, not a pass. Superiority that only appears on the tuning split is not
superiority.

---

## 4. Non-goals (explicit — prevents drift)

- **Not** a general agent framework, IDE, or chatbot. No feature earns its place unless it serves
  truth-gated reproduction-and-verification of evidence-synthesis work.
- **Not** "most agents" or "most autonomy" — arm B exists precisely to refuse the "more agents = better"
  story unless measured.
- **Not** a novelty collector. Techniques from the research doc are candidate *mechanisms*, adopted only
  if the §3 benchmark shows efficacy/cost improvement with zero regression (T-HE discipline).
- **Not** self-mutating over production on day one. Human-in-the-loop promotion; the autonomous
  Proposer is a north-star gated on the Evaluator being trustworthy.
- **Not** a claim of superiority we cannot currently prove. Until §3 runs on held-out data, "world-class"
  is a *target*, not a stated result.
- **Not** a second control plane. All control runs through Dispatch (§0.5 / D7); no bespoke control
  daemon is added alongside it.
- **Not** a weak-model panel. Reasoning / reproduction / verification seats are **frontier-only**
  (§1.5); cheap models are excluded from those seats, and are a *tested* option only in the narrow
  Dispatch routing seat.

---

## 5. Governance (how a change earns "world-class")

Every harness change is: **additive / behind a flag / shadow-mode first** → measured **zero-regression**
shadow phase → enforce, with **one-flag rollback** and the prior code path intact for one full nightly.
A change is *promoted* only when it beats the incumbent on the §3 **blended score on held-out evals**
(T-HE). Build-order discipline governs sequencing: **manual-reliable → Skill → loop(gate+stop) → then
schedule.** Single-writer-per-repo; no force-push; gated commits.

**Two-slice frozen-benchmark rule (AN-2, arXiv:2605.30621 "Harness Updating Is Not Harness Benefit").**
Benchmark-gated evolution can manufacture *illusory* progress by overfitting the gate — "harness
updating" masquerading as "harness benefit". Fence: the §3 corpus is split three ways by a deterministic
sha256 bucket — **dev** (tuning), **held-out** (scored each run), and a **FROZEN** slice that
harness-evolution **never reads, scores against, or tunes on**. A candidate harness change is promoted
only if it beats the incumbent on the held-out slice **and** on the frozen slice
(`scoring.two_slice_promotion`); a held-out-only win is rejected as eval-fit. The frozen slice is off the
*evolution* surface (distinct from keys being off the *agent* surface). **Live in the harness now**
(`tasks.frozen_ids`; the scorecard reports the sealed frozen numbers for reference), so the first real
A/B/C run is honest by construction.

*This spec is the yardstick. `GAP_ANALYSIS.md` measures the current code against it; `ROADMAP.md`
sequences the no-regression path to satisfying every differentiator, with §3 as the acceptance test;
`BEST_IN_CLASS_WORKFLOW.md` maps the full end-to-end pipeline (problem → moat → method → cross-vendor
verification → benchmark → publish) as Dispatch-orchestrated, loop-engineered stages.*
