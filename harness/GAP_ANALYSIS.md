# GAP_ANALYSIS — current harness vs WORLD_CLASS_SPEC

**Date:** 2026-07-04
**Method:** read-only inventory of the live working tree (`F:\overmind\overmind`) on
2026-07-04, cross-checked against the 2026-07-04 research doc (`workflow-upgrade/`) which itself
verified file:line references. Every "meets/partial/missing" below carries code evidence.
**Baseline at time of writing:** `tests/unit` = **909 passed, 8 skipped** (pre-increment);
**968 passed, 8 skipped** after the three increments in this session (no regression).

**Headline:** *The verdict **logic** is frontier-grade; the gaps are (1) no objective-gate floor
recorded under consensus, (2) no real cost-per-accepted-change, and (3) cross-vendor reproduction
proven-by-hand but not a standing recorded stage. All three are additive to close — and the
first, cheapest slices of each shipped this session behind flags.*

---

## Scorecard against the six differentiators

| Diff | Bar (from spec) | Verdict | Evidence |
|---|---|---|---|
| **D1** Cross-vendor consensus-or-flag | ≥2 independent families on every ship verdict, recorded; disagreement flags | **PARTIAL** | Machinery exists: `judge_factory.enforce_distinct_families`, `family_for_engine`, `estimate_effective_votes` (`judge_factory.py:98-200`); `multi_persona.preferred_runner_for` keeps reviewer≠writer (`multi_persona.py:52-63`). **But** the cross-vendor check is not recorded as a first-class per-verdict field, and runtime auth often collapses the panel to 1 live engine with no loud signal (research doc §1.1). |
| **D2** Objective truth-gate floor | objective witness under every accept, or human-in-chair | **PARTIAL — biggest gap** | Real objective witnesses exist (`verifier.py` allowlist+exit codes, `browser_checks.py`, numeric/continuity witnesses, R-parity). **But** the headline verdict can rest on the judge alone: `orchestrator.py:781` (judge FAIL only counts at conf≥0.7), `_judge_enabled` default False (`orchestrator.py:816-822`), and `_trajectory_fast_path_result` ships success on a probability with **no witness** (`orchestrator.py:835-856`). Nothing counted how often. |
| **D3** Reproduction-or-flag | independent reproduction per quantitative claim, recorded | **PARTIAL** | Proven end-to-end manually (triple-vendor transport-NMA to full precision, per memory `cross-engine-corroboration-2026-06-25`); numeric/continuity witnesses exist. **But** there is no standing, per-claim *recorded* independent-reproduction stage wired into the nightly path. |
| **D4** Full auditability / provenance | span/provenance on every verdict | **PARTIAL** | Excellent audit artifacts: signed cert bundles (`cert_bundle`, freshness/replay tests green), JSONL finding streams, `verdict_trace.py` (OTel-shaped tracer). **But** the tracer is *not threaded through* — most callers pass `tracer=None` (research doc §1.1); `meta_verification` is a manual tool, never called by the nightly runner. |
| **D5** Cost-per-accepted-change | real cost-per-accepted per loop; break-even flag; hard ceiling | **MISSING → now PARTIAL** | Before: only a rough hardcoded estimate (`nightly/runner.py:443` `_run_cost_usd`, `_COST_PER_UPGRADE_USD`/`_COST_PER_REPAIR_USD` at `:790,:914`); no `total_cost_usd` parse, no acceptance rate. **This session** added `telemetry/cost_accounting.py` (real `total_cost_usd` parse + acceptance rate + break-even flag) — instrument exists; not yet wired into the nightly loop. |
| **D6** Private eval / ground-truth moat | blinded, growing private corpus as the scorer; §3 benchmark standing | **PARTIAL** | Corpus + evals exist (`intelligence/gold_benchmark.py`, `intelligence/eval_harness.py`, `evals/` with 11+ measured evals, AACT/gold-MA/R-parity assets). **But** the §3 MADE-style closed-loop A/B/C benchmark is not yet standing, and run-time blinding of the answer key is not enforced as a rule. |
| **D7** Dispatch as single control plane | one plane; gate before accept; reroute on cap; provenance per claim | **PARTIAL** | Dispatch orchestrator + scheduled agent-drain-watchdog proven in production (spawns/steers lanes, cross-vendor witness, relaunch-to-cap). **But** control flows are not yet expressed as a *recorded Dispatch provenance* per verdict, and the objective-gate floor (D2) is not yet enforced at the Dispatch **accept** point. |
| **§1.5** Frontier-only vendor panel, qualified on hardest tasks | each seat's model qualified on the HARDEST tasks; marginal value measured | **PARTIAL** | Frontier seats configured (Claude Opus-class, Codex gpt-5.5 ×2, agy/Gemini). **But** no **capability-cliff qualification eval** (fitness judged on hard tasks, where weak-model collapse is visible), no per-vendor **marginal-value** measurement, and **Sonnet-top-as-verifier is untested**. |

---

## What already MEETS the bar (do not rebuild)

- **State outside the conversation (Loop-Engineering STATE):** atomic `.progress_<date>.json`,
  hash-skip cache, heartbeat files, `circuit_states.json`, Sentinel/Overmind `STUCK_FAILURES.jsonl`.
- **Family decorrelation as hard enforcement:** `enforce_distinct_families` drops same-family
  redundancy and rejects a quorum with <2 families (`judge_factory.py:148-200`) — the structural
  core of D1 is present and unit-tested (`test_judge_factory.py`).
- **Objective witnesses themselves:** the verifier's command allowlist + exit-code gating
  (`verifier.py`), browser/Playwright checks, numeric-continuity, R-parity, Sentinel BLOCK — the
  *ingredients* of D2/D3 exist; what was missing is the *floor assertion* that one of them ran.
- **Audit trail:** signed bundles with freshness/replay protection; the `UNVERIFIED` verdict
  distinct from PASS for numerical-SKIP (the SKIP-as-pass lesson is already encoded).
- **Heartbeat/automation + Skills:** nightly runner, scheduled SKILL.md tasks, `SkillLibrary`.

## What is PARTIAL (proven but not standing / not recorded)

- Cross-vendor check runs by hand but isn't a recorded per-verdict field (D1).
- Reproduction proven manually, not a standing recorded stage (D3).
- Tracer built but not threaded; `meta_verification` never auto-runs (D4).

## What was MISSING (and the first slice shipped this session)

- **Objective-gate floor (D2):** no code asked "did an objective witness decide this success?"
  → **shipped** `verification/objective_gate.py` (shadow WARN, wired into `orchestrator.py` behind
  `OVERMIND_OBJECTIVE_GATE_AUDIT`, never mutates a verdict).
- **Cost-per-accepted-change (D5):** no real spend instrument → **shipped**
  `telemetry/cost_accounting.py` (real `total_cost_usd` parse, acceptance rate, break-even flag).
- **First-class cross-vendor stage (D1):** proven-by-hand only → **shipped**
  `verification/cross_vendor_check.py` (advisory, decorrelation-enforced, `AUTH_DEGRADED` when no
  live different-family checker) + the additive `CodexBackend.effort` knob.

---

## Live reward-hacks the spec's fences must close (named, with evidence)

These are *targets without fences* (LFD discipline) — each needs an objective instrument:

1. **Judge-only ship** — `orchestrator.py:781` low-confidence FAIL-as-PASS; `_judge_enabled` default
   False. *Fence:* the D2 objective-gate audit (shipped as WARN this session; promotion path defined).
2. **Trajectory fast-path pass with no witness** — `orchestrator.py:835-856`. *Fence:* same audit
   flags `trajectory_fast_path`-only successes (covered by `test_objective_gate.py`).
3. **`compound_judge` empty-steps → passed=True** (research doc §1.1). *Fence:* objective-gate audit
   + a future empty-steps guard.
4. **`injection_clean_boundary` 100% false-PASS** on the probe (research doc §2 T7). *Fence:*
   credibility/debate judge (Step 5, measurement-gated) — not yet addressed.
5. **RapidMeta `cE>cN` at-scale** — impossible 2×2 cells in ~hundreds of generated dashboards.
   *Fence:* the cross-vendor bug-hunt canary (shipped stage; the `cE>cN` fixture is its planted-bug
   acceptance target) + a hard `events≤N` denominator gate (future).
6. **Found-nothing pass** — a bug-hunt that finds nothing counts as clean. *Fence:* the planted-bug
   canary in the §3 benchmark (a found-nothing pass on a fix task is a *failure*).

---

## Bottom line

The harness is **one honest step from provable** on D2 and D5 and **two** from D1/D3: the
mechanisms exist or shipped this session; what remains is (a) run the shadow WARN cycle to quantify
D2, (b) wire the cost instrument into the nightly loop for D5, (c) make the cross-vendor stage a
recorded per-verdict field for D1, and (d) stand up the §3 benchmark on the private corpus so
"world-class for its purpose" stops being a target and becomes a measured result. `ROADMAP.md`
sequences exactly that, no-regression.
