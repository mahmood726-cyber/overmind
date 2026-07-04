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

## 1. The 4–6 differentiators (what makes it best-in-class FOR THIS PURPOSE)

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

**Why exactly these six:** D1–D3 are the *correctness* core (independent, gated, reproduced);
D4 is the *trust* layer (auditable); D5 is the *economics* that keep it usable; D6 is the *moat*
that makes the whole thing defensible and measurable. Drop any one and the claim "best-in-the-world
for its purpose" stops being provable.

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
   objective-gate floor (D2) + reproduction-or-flag (D3), under the same budget.

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
- **Efficiency:**
  - **cost-per-accepted-change** = total USD spend / number of accepted-and-correct changes
    (from real `total_cost_usd` + Codex/agy usage — D5).
  - **wall-clock per accepted change** and **tokens per accepted change** (secondary).
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

---

## 5. Governance (how a change earns "world-class")

Every harness change is: **additive / behind a flag / shadow-mode first** → measured **zero-regression**
shadow phase → enforce, with **one-flag rollback** and the prior code path intact for one full nightly.
A change is *promoted* only when it beats the incumbent on the §3 **blended score on held-out evals**
(T-HE). Build-order discipline governs sequencing: **manual-reliable → Skill → loop(gate+stop) → then
schedule.** Single-writer-per-repo; no force-push; gated commits.

*This spec is the yardstick. `GAP_ANALYSIS.md` measures the current code against it; `ROADMAP.md`
sequences the no-regression path to satisfying every differentiator, with §3 as the acceptance test.*
