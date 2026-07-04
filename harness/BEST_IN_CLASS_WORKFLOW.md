# BEST_IN_CLASS_WORKFLOW — the end-to-end pipeline, loop-engineered

**Date:** 2026-07-04
**Status:** canonical blueprint. Companion to `WORLD_CLASS_SPEC.md` (the control-plane + differentiator
spec). This document maps Mahmood's **entire workflow** — truth-recovery in evidence-synthesis methods
research + the RapidMeta app pipeline — as a set of **loop-engineered, Dispatch-orchestrated,
cross-vendor-verified, benchmark-gated stages**, synthesizing every source gathered this session.
**Purpose-anchored, truth-first, no-regression.** The benchmark that proves superiority is designed so
it *can show us not winning*.

**Sources synthesized** (all in `F:\overmind\workflow-upgrade\2026-07-04-implementation-checklist.md`
and `F:\overmind\vault\00-Sources\`): evolve-the-harness (Niklaus), Loop Library, MADE benchmark,
scheduler-graph (SGH), Trinity router, LFD / loss-functions + reward-hacking fences (Elvis Sun),
Claude Code primitives, MemClaw + AutoMem (memory), Ragas (extraction eval), mattpocock/sanyuan skills,
and "Right in the Right Way" (MIT, RLVR + human-demos anti-reward-hacking).

---

## 0. The three invariants under every stage

1. **Dispatch is the conductor** (`WORLD_CLASS_SPEC` §0.5 / D7). Every stage is a **Dispatch-orchestrated
   flow**: Dispatch routes each unit to the strongest live *frontier* vendor on the right node, gates
   the result, and moves on. Vendor lanes are stateless workers. Primitives:
   `start_task`/`start_code_task`/`send_message` (drive), `read_transcript`/`list_sessions` +
   the scheduled **agent-drain-watchdog** (observe → relaunch/refill to cap).
2. **Every stage is a loop with an objective gate + a stop condition + external state**
   (Loop-Engineering / Cherny; Loop Library). "Verify" = an *objective* gate (test / diff / R-parity /
   `node --check`), **not** a second agent agreeing. State lives outside the conversation (files are the
   floor; MemClaw is the machine mirror; the vault is the human mirror).
3. **Every loop has a fenced loss function** (LFD / Elvis Sun; reinforced by RLVR+human-demos, MIT):
   TARGET (descend, blinded) · CONSTRAINTS (budget/wall-clock/surface) · INSTRUMENTS (the objective
   gate that makes a constraint real) · FORCED-ENTROPY (overfit reflection / stall break). *"Every cheap
   path you don't fence off is a direction the optimizer sprints down."* The cross-vendor check is the
   harder-to-game complement to any single objective scalar (MIT finding: a lone verifiable reward gets
   hacked; a second, harder-to-game signal nearly eliminates it).
4. **Gate-output contract (AN-8, Osmani "Agent Harness Engineering"):** **success is silent, failures
   verbose** — a passing gate emits nothing; a failing gate re-injects verbose diagnostics (the failed
   typecheck/diff/parity output) as the objective signal. And the **ratchet rule**: every harness rule
   cites the specific failure that motivated it (formalizes `lessons.md`) — a rule with no cited failure
   is not a rule.

---

## 1. Stage map (the pipeline)

Each stage: **the cutting-edge idea powering it · objective GATE · STOP condition · external STATE ·
the fence against its reward-hack.** Frontier models only on reasoning/reproduction/verification;
Dispatch routes.

### Stage 1 — Problem / idea selection (groundbreaking-oriented)
- **Idea:** bias to **novel, defensible method problems** (the moat starts at problem choice). Loop
  Library "research-to-artifact" template; scientific-problem-selection discipline.
- **GATE:** a candidate problem is admissible only if (a) it has a **private ground-truth path** (Stage
  2 can build an eval nobody else can score against) and (b) a **named primary estimand** with a
  reproduction target. No eval path → not admissible.
- **STOP:** a shortlist of ≤N problems each with a stated estimand + eval path; or "nothing novel &
  defensible surfaced → stop, don't churn."
- **STATE:** problem register in the vault (`03-Decisions`), mirrored to MemClaw.
- **FENCE:** reward-hack = "pick an easy problem that scores well." Fence = admissibility requires the
  hardest-task eval path, not a demo.

### Stage 2 — Ground-truth / private-eval acquisition (THE MOAT + the loss function)
- **Idea:** the **private eval IS the moat** (LFD: *"the eval nobody else can score against"*). Build
  from **AACT registered-vs-published**, the **gold-MA library**, **R/metafor parity** fixtures.
  Ragas generates/scoring **extraction-fidelity** eval cases from our own corpus (faithfulness =
  extracted number matches source page) — but only as a **WARN-tier** complement; deterministic
  gates (byte/numeric diff, R-parity) stay the floor.
- **GATE:** each eval item has a **verifiable answer key** and is **blinded to the agent at run time**
  (answer key outside the agent's tool/file surface — Niklaus "never read the test split", LFD Target
  rule #1). Extraction items pass a **hard** check, not just a Ragas LLM-judge score.
- **STOP:** eval set large enough that **enumeration doesn't pay** + a held-out split reserved; the
  RapidMeta `cE>cN` planted-defect canary exists.
- **STATE:** versioned corpus; held-out split sealed; growth log (T8 auto-promotes production failures
  into fixtures — the moat compounds).
- **FENCE:** reward-hacks = *memorize the eval*, *mine miss-lists into lookup tables*, *game the judge*
  (Elvis Sun's three observed cheats; MIT confirms reward-hacking is real). Fences = blinding, a large
  target, deterministic instruments, and a **found-nothing-pass canary**.

### Stage 3 — Method development (frontier models, no weak models on hard reasoning)
- **Idea:** develop the methods — **AdaptShrink, transport-NMA / registry-borrowing, DTA,
  dose-response, consensus-or-flag** — with **frontier models only** (§1.5). The inner loop is
  spec-driven "make the tests pass" (mattpocock `tdd`: red-green-refactor, one vertical slice).
- **GATE:** the method's own test suite green + `node --check`/build + the numeric fixtures from Stage 2.
  This is the **objective inner-loop gate** (LFD inner loop terminates on green).
- **STOP:** all method fixtures green **and** the primary estimand reproduces on the dev split; or
  iteration cap → log blocker to `STUCK_FAILURES`.
- **STATE:** repo + `.progress_<date>.json`; single-writer-per-repo (SOP); gated-additive-deploy SOP.
- **FENCE:** reward-hack = "make tests pass by weakening the test / hardcoding the fixture." Fence =
  identifier/date/stat cross-checks (AGENTS.md rules) + the Stage-4 cross-vendor check that a human/
  different vendor reads the diff.

### Stage 4 — Cross-vendor VERIFICATION (THE CROWN)
- **Idea:** **consensus-or-flag on frontier-heterogeneous models** (Claude / GPT-via-Codex /
  Gemini-via-agy) with an **objective-gate FLOOR beneath every "pass"** (D2), **reproduce-or-flag**
  (D3, independent re-derivation to declared precision), and **full provenance** (D4). Trinity
  acceptance loop (run until the Verifier ACCEPTs); family-decorrelation (`enforce_distinct_families`);
  our proven triple-vendor witness. Codex = strongest bug-finder lane (xhigh effort).
- **GATE (the floor):** Dispatch **does not accept any lane's "pass" without a named objective witness
  under it** — test / byte-or-numeric diff / R-parity / `node --check` / Playwright. A judge/consensus
  agreement alone is **flagged, not shipped** (the shipped `objective_gate.py` audit; promoted to a
  hard requirement here). Disagreement between vendors **flags** for human-in-the-chair.
- **check≠repair separation (AN-4, Proof Gates arXiv:2605.17998):** the verify stage is **read-only** —
  it emits PASS/FAIL **+ a reproducibility snapshot** and may **never silently edit the artifact to
  pass**. "Once the admission verifier becomes a worker, independent confirmation turns into
  self-repair." A stage that produces no reproducibility snapshot is **downgraded one trust tier**.
- **clean-context verification (AN-9, Cognition Apr 2026):** the verifier receives **artifact + objective
  spec ONLY**, not the producer's reasoning trace — so it cannot inherit the generator's rationalizations.
  Cross-vendor escalation is a **capability-router (delegate a hard call to a stronger *frontier* model),
  not a difficulty-escalator** (never escalate to a weaker/cheaper model to get an easier pass).
- **n_eff decorrelation sub-gate (AN-3):** cross-vendor agreement counts as consensus only if the
  agreeing judges' Kish `n_eff ≥ 2` across ≥2 families; otherwise fall through to the objective witness.
- **STOP:** Loop Library convergence/Clodex stop — *"only when both approve the same unchanged version"*
  / *"when the checker approves, only accepted findings remain, progress stalls, or the iteration cap is
  reached."*
- **STATE:** signed cert bundle (freshness/replay-protected) + JSONL findings + the per-verdict
  `cross_vendor_check_present(vendor=…, decorrelated=…)` field + Dispatch provenance record.
- **FENCE:** reward-hacks = *found-nothing pass*, *correlated agents rubber-stamp*, *judge gamed by
  phrasing*, *generating agent games its own verification* (test-weakening, fixture-hardcoding,
  `sys.exit(0)`, validator-patching). Fences = the planted-bug canary (a found-nothing pass on a fix
  task = failure); frontier-only decorrelated panel (weak models fail correlated → excluded); the
  marginal-value metric that drops a rubber-stamping vendor (§1.5.3); and the **AN-6 eval-gaming
  pre-filter** (`verification/eval_gaming_filter.py`, clean-room regex+AST layer inspired by
  rewardhackwatch, trajectory-only, no code exec) run as a cheap advisory over any PASS before it
  ships. **This stage is where D1+D2+D3+D4 all bind.**

### Stage 5 — Benchmark vs comparators + the harness benchmark (THE PROOF)
- **Idea:** two proofs. (a) **beat-all vs published comparators** on the method's own metric; (b) the
  **MADE-style constrained-budget A/B/C harness benchmark** (`WORLD_CLASS_SPEC` §3): heterogeneous
  truth-gated (ours) vs single-agent vs homogeneous-multi, on the private corpus, held-out split,
  scored on correctness/agreement **and** cost-per-accepted-change.
- **GATE:** superiority is decided on the **held-out** blended score (efficacy − false-alarm + parity −
  cost); weights + cost-multiple **pinned before the run**. Panel members pass the **capability-cliff
  qualification** on the hardest tasks first.
- **STOP:** the benchmark produces a signed scorecard with the win-condition verdict — *including the
  honest failure outcomes* (B≈C → heterogeneity not paying; cost≫A → not affordable; high false-alarm →
  crying wolf). The benchmark **can report that we do not win.**
- **STATE:** versioned scorecard; per-vendor marginal-value table; regression snapshot (rollback if any
  metric regresses >2%).
- **FENCE:** reward-hacks = *overfit the dev split*, *inflate one blended term while regressing another*.
  Fences = held-out decision only, one-mechanism-per-change, pinned weights.

### Stage 6 — Publish (Synthēsis papers, manuscripts, RapidMeta apps)
- **Idea:** ship with the **same truth-gates** — no manuscript/app claim ships without its Stage-4
  cross-vendor + objective-gate provenance. Editorial-board separation SOP for Synthēsis. RapidMeta
  apps carry the R-parity + `events≤N` denominator gate (the `cE>cN` class).
- **GATE:** every important claim traces to a source (Loop Library research-to-artifact proof: *"claims
  trace to sources, uncertainty is explicit"*); no placeholder leaks (the 3-layer defense); Sentinel
  BLOCK clean.
- **STOP:** artifact meets acceptance criteria (all claims sourced, gates green) or "blocked/exhausted".
- **STATE:** GitHub + Pages + `E156-PROTOCOL.md`; INDEX.md / workbook updated (registry gates).
- **FENCE:** reward-hack = marketing overclaim ("Global/Full/Complete" without implementation). Fence =
  the no-marketing rule + grep of source row-counts before doc generation.

---

## 2. The two cross-cutting layers (span all stages)

### Memory — a first-class EVOLVING layer (not static)
- **AutoMem principle (Stanford, arXiv 2607.01224):** memory decisions (*when/what to store, how to
  retrieve*) are a **learnable, evolvable skill distilled from our own trajectories** — not a fixed
  hand-tuned store. The vault/MemClaw/SOP layer **should not sit static**; the "manage your own memory"
  policy evolves with task experience. (Adopt the *framing*, not the training pipeline — truth-first.)
- **MemClaw (Caura, Apache-2.0):** the **machine-readable shared store** — the concrete tool for the
  missing shared-signal bus. Mirror `STUCK_FAILURES.jsonl` / `.progress_<date>.json` /
  `circuit_states.json` into MemClaw **additively** (files stay source-of-truth / audit floor);
  contradiction-detection surfaces correlated-loop conflicts (ties to LFD).
- **Vault (Obsidian):** the **human-readable** mirror (`F:\overmind\vault`).
- **Loop:** every stage writes signals other stages read (shared signal store); memory-policy quality
  is itself measured and improved (AutoMem outer loop = evolve-the-harness applied to memory).

### The harness itself EVOLVES (Niklaus — evolve-the-harness, benchmark-gated)
- **Outer meta-loop:** propose **one mechanism** per iteration → evaluate on the Stage-5 benchmark →
  keep only if it beats the incumbent on the **held-out blended score with zero regression** (T-HE).
  *"Five of the top six harnesses are deterministic code, not prompt edits"* — prefer
  deterministic/robustness mechanisms (they transfer across vendors; prompt playbooks are
  vendor-specific and can backfire — directly relevant to our heterogeneous panel).
- **Execution substrate:** SGH scheduler-graph *concepts* (dependency-aware routing via
  `ContractImpactGraph`; bounded escalation Retry→Patch→Replan; `any_of` cross-vendor racing) — adopted
  as concepts, evidence-light position paper, never cited as measured gains.
- **The conductor:** Dispatch (Trinity-validated light router over a frontier pool).

---

## 3. Gap vs current (honest)

| Stage / layer | Meets today | Gap |
|---|---|---|
| 1 Problem selection | done ad-hoc by Mahmood | admissibility (eval-path required) not enforced as a gate |
| 2 Ground-truth moat | corpus + evals exist (`gold_benchmark`, `eval_harness`, AACT/gold-MA) | **run-time blinding not enforced**; Ragas extraction-eval not wired; growth (T8) not automated |
| 3 Method dev | strong (methods repos, `tdd`-style, objective test gates) | fine |
| 4 Cross-vendor verification | **proven** (triple-vendor NMA); machinery exists; **stage shipped this session** (`cross_vendor_check.py`, advisory) | not yet a **recorded per-verdict field**; objective-gate floor is WARN, not enforced at accept; runtime auth can collapse the panel |
| 5 Benchmark | evals harness + 11 measured evals; comparators run per-method | **§3 A/B/C harness benchmark not standing**; capability-cliff qualification not built; per-vendor marginal-value not measured |
| 6 Publish | mature (E156 pipeline, Sentinel, Pages) | apply Stage-4 provenance as a hard publish gate |
| Memory | files + vault + (some) MemClaw mirror | memory-policy not **evolving**; MemClaw mirror not standing; shared signal bus partial |
| Evolve-harness | no-regression discipline in place | **automated benchmark-gated loop not standing** (needs Stage 5 trustworthy) |
| Dispatch control plane | orchestrator + drain-watchdog **proven in production** | control flows not expressed as **recorded Dispatch provenance**; objective-gate floor not enforced at the Dispatch accept point |
| Model selection | frontier seats configured | **capability-cliff qualification eval missing**; Sonnet-top-as-verifier untested; marginal-value not measured |

---

## 4. No-regression rollout ordering (additive, flag-gated, shadow-first)

Governed by build-order: **manual-reliable → Skill → loop(gate+stop) → then schedule**, and by the
zero-regression rule (one flag, shadow → measured no-regression → enforce, one-flag rollback).

1. **(shipped, Milestone 0)** objective-gate floor audit (Stage 4, WARN) · cost-per-accepted instrument
   (Stage 5) · cross-vendor check stage (Stage 4, advisory) — all behind flags, 968/8 tests green.
2. **Run the Stage-4 objective-gate WARN cycle + thread provenance (D4/D7).** Quantify judge-only ships;
   start recording a Dispatch provenance record on each verdict.
3. **Wire cost-per-accepted into the Dispatch accept point (Stage 5/D5).** Real `total_cost_usd`; surface
   below-break-even per loop.
4. **Make the cross-vendor check a recorded per-verdict field + prove the `cE>cN` canary (Stage 4/D1).**
   Confirm both Codex seats answer a low-effort smoke probe first.
5. **Enforce the objective-gate floor at Dispatch accept (Stage 4/D2 promotion)** — only after the WARN
   cycle quantifies the gap; reuse the `UNVERIFIED` verdict, never a silent pass.
6. **Build the capability-cliff qualification eval + per-vendor marginal-value (Stage 5/§1.5)** on the
   hardest tasks; test Sonnet-top as verifier; drop rubber-stampers.
7. **Stand up the §3 A/B/C harness benchmark on the private corpus (Stage 5/D6)** — the acceptance test.
8. **Memory-as-evolving-layer (AutoMem framing) + MemClaw shared store mirror**, additive/read-only first.
9. **Automated evolve-the-harness loop (T-HE), human-in-the-loop first**, gated on Stage 7 being trustworthy.

---

## 5. The honest benchmark (restated — it can show us NOT winning)

Superiority is *only* claimed after the Stage-5 §3 benchmark runs on **held-out** data with pinned
weights, showing arm C beats single-agent (A) and homogeneous-multi (B) on caught-defect + agreement
soundness at an affordable cost-per-accepted — **and** each panel member earns its seat by marginal
error-catching on the hardest tasks. If B ≈ C, or cost ≫ A, or false-alarms are high, the benchmark
**says so**. Until then, "best-in-class" is a target, not a result. That is the truth-first position the
whole program is built to defend.

*Companion docs: `WORLD_CLASS_SPEC.md` (control plane + differentiators + benchmark), `GAP_ANALYSIS.md`
(code-level gaps), `ROADMAP.md` (increment sequencing). Source syntheses: `F:\overmind\vault\00-Sources\`.*
