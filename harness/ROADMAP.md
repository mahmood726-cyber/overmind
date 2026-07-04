# ROADMAP — no-regression path to world-class (for its purpose)

**Date:** 2026-07-04
**Acceptance test for the whole program:** the §3 benchmark in `WORLD_CLASS_SPEC.md` — the MADE-style
constrained-budget closed-loop A/B/C eval on the private corpus, decided on a held-out split. A
milestone is "done" only when it is additive, flag-gated, shadow-proven zero-regression, and (for
enforcement steps) shown to beat the incumbent on the §3 blended score on **held-out** evals.

**Governing rules:** one mechanism per change · behind one flag · shadow → measured zero-regression →
enforce · one-flag rollback · prior code path intact for one nightly · single-writer-per-repo · no
force-push · build-order: manual-reliable → Skill → loop(gate+stop) → then schedule.

---

## Milestone 0 — SHIPPED this session (additive, flagged, tests green)

| Increment | Module | Flag (default) | State |
|---|---|---|---|
| **D2** objective-gate floor audit | `verification/objective_gate.py` + `core/orchestrator.py` hook | `OVERMIND_OBJECTIVE_GATE_AUDIT=shadow` | WARN-only; never mutates a verdict; 27 tests |
| **D5** cost-per-accepted-change instrument | `telemetry/cost_accounting.py` | (library; opt-in per loop) | real `total_cost_usd` parse + acceptance rate + break-even flag; 19 tests |
| **D1** cross-vendor check stage | `verification/cross_vendor_check.py` + `CodexBackend.effort` | `OVERMIND_CROSS_VENDOR_CHECK=off` | advisory, decorrelation-enforced, `AUTH_DEGRADED` when no live different-family checker; 13 tests |

Full unit suite: **968 passed / 8 skipped** (baseline 909/8) — **no regression**. Rollback = unset the
flag / don't construct the ledger; every prior code path is byte-unchanged (CodexBackend `effort=None`
is byte-identical).

---

## Milestone 1 — SHIPPED (the first 3 moves; additive, flagged, tests green)

| Move | Modules | Flag (default) | Tests | Now measurable |
|---|---|---|---|---|
| **1. Accept-point provenance + WARN-cycle quantifier** (D7/D4/D2) | `verification/provenance.py` + orchestrator accept-point hook | `OVERMIND_PROVENANCE=off` | +18 | per verdict: worker vendor+family, deciding gate, would-ship-without-gate; aggregate % of ships resting on consensus alone |
| **2. Cost-per-accepted-change at the accept point** (D5) | `telemetry/cost_accounting.py` (`cost_event_from_output`) + orchestrator per-run ledger | `OVERMIND_COST_ACCOUNTING=off` | +13 | real/estimated USD per accepted change, acceptance rate, below-break-even per loop |
| **3. Cross-vendor check as recorded per-verdict field + cE>cN canary + Codex smoke probe** (D1) | `verification/cross_vendor_check.py` (`smoke_probe_codex_seats`, `CANARY_ARTIFACT`, `is_found_nothing_pass`) + orchestrator | `OVERMIND_CROSS_VENDOR_CHECK=off` | +8 | per verdict: did an independent different-family vendor review it + what it found; seat liveness; found-nothing-pass canary |

Commits: `e1d882c` (1), `cff9fb7` (2), `373e4ee` (3). Full unit+integration **1043 passed / 9
skipped** (Milestone-0 baseline 1022). No regression; every hook default-off and wrapped so it can
never wedge the accept path.

## The next steps from here (in order)

### Step 1 — Run the D2 objective-gate WARN cycle + thread the tracer (D4 prerequisite)
- **Do:** run one full nightly with `OVERMIND_OBJECTIVE_GATE_AUDIT=shadow` on; collect the tally
  "N of M success verdicts had an objective witness; K relied on judge/heuristic alone", and the K
  list. Spot-check ≥5 flagged verdicts by hand (done-check: no false WARNs on ships that had a real
  test/build/diff witness). In the same pass, start threading `verdict_trace.py` through the
  orchestrator/verifier hot paths so the audit fields are queryable, not just logged.
- **Gate:** a produced, believable tally + non-empty spans on a traced verdict.
- **Risk:** very low (observational). **Rollback:** unset the flag; tracer no-ops when absent.

### Step 2 — Wire the D5 cost instrument into the nightly loop (real spend, per loop)
- **Do:** replace the hardcoded `_run_cost_usd` estimate (`nightly/runner.py:443,790,914`) with a
  `CostLedger` fed by real `claude -p --output-format json` `total_cost_usd` and Codex/agy usage
  estimates; record accept/reject per project; surface cost-per-accepted-change and the
  below-break-even heuristic per loop in the daily report. Keep the old estimate path behind the flag
  for one nightly to confirm the new number is sane.
- **Gate:** one nightly emits a cost-per-accepted-change figure per loop; the hard money ceiling still
  fires at the same point it does today.
- **Risk:** low (additive emission + a swap of the accumulator source). **Rollback:** flag reverts to
  the estimate accumulator.

### Step 3 — Make the D1 cross-vendor check a recorded per-verdict field (T-CV, advisory)
- **Do:** call `CrossVendorChecker` in the nightly verification phase (behind
  `OVERMIND_CROSS_VENDOR_CHECK=shadow`), record `cross_vendor_check_present(vendor=…, decorrelated=…)`
  on every ship verdict and in the cert bundle; findings land as `sentinel-findings`-style advisories,
  never ship-blocking. Prove signal on the RapidMeta `cE>cN` planted-bug fixture (a found-nothing pass
  fails the canary). Prerequisite: confirm both Codex seats answer a low-effort smoke probe (auth live).
- **Gate:** every ship verdict carries a cross-vendor-check-present field; checker family ≠ maker
  family in 100% of cases; the canary catches the planted `cE>cN` bug.
- **Risk:** low by design (advisory, additive, cross-vendor). **Rollback:** unset the flag → no output.

---

## Later phases (measurement-gated; each additive + shadow-first)

- **Phase A — Reproduction-or-flag as a standing stage (D3).** Wire an independent-reproduction
  witness per quantitative claim (byte/numeric parity via a different vendor) into the nightly path;
  record the reproduction witness id on the verdict. Shadow-compare against current numeric witnesses.
- **Phase B — Auth preflight + node breaker/backoff (T5/T6), durable dispatch journal (T4).** Cluster
  branch; shadow against dead-key/flapping-node fixtures and injected-crash replay. Gates the cluster
  branch's merge.
- **Phase B2 — Dispatch as recorded control plane (D7).** Express the accept/reroute/provenance logic
  as Dispatch flows: record a Dispatch provenance record (vendor, node, gate outcome, cost) on every
  verdict; enforce the objective-gate floor (D2) at the Dispatch accept point; prove reroute-on-cap to
  a non-capped vendor with no lost work. Additive; shadow-recorded before enforced.
- **Phase B3 — Frontier model-selection eval (§1.5).** Build the **capability-cliff qualification** on
  the hardest tasks (multi-arm NMA parity, DTA bivariate, borrowing-field k-fold, long agentic
  bug-hunts); measure **per-vendor marginal value** (drop-one ablation) + rubber-stamp rate; **test
  Sonnet-top as a cheaper verifier** (kept only if it holds on the cliff). Frontier-only, non-diluted.
- **Phase C — Stand up the §3 benchmark (the T-HE Evaluator) on the private corpus (D6).** Build the
  A/B/C arms (all run through Dispatch; they differ only in what Dispatch orchestrates), pin weights +
  cost multiple K *before* running, enforce held-out blinding (answer key outside the agent's tool
  surface). This is the acceptance test the whole program is measured by. See the full end-to-end
  pipeline in `BEST_IN_CLASS_WORKFLOW.md`.
- **Phase D — Research track, measurement-gated last (T7/T8/T9/T10-DAG).** Credibility/debate judge,
  failure→regression auto-promotion, explicit handoffs, DAG scheduler concepts — each must **beat the
  incumbent on the §3 held-out blended score or produce identical verdicts** before touching a ship path.
- **Phase E — Harness-evolution loop automation (T-HE north-star).** Only after the §3 Evaluator is
  trustworthy: a human-in-the-loop-then-autonomous Proposer that adds one mechanism per iteration,
  kept only on a held-out blended-score win. Never reads the held-out split. **Two-slice frozen rule
  (AN-2, live now):** a candidate is promoted only if it also wins on the SEALED frozen slice that
  evolution never reads/scores/tunes on (`tasks.frozen_ids` + `scoring.two_slice_promotion`) — a
  held-out-only win is eval-fit, not benefit (arXiv:2605.30621).

---

## Honest risks (stated, not buried)

1. **The benchmark could show us NOT winning.** If arm B (homogeneous multi-agent) ≈ arm C, vendor
   diversity (D1) isn't paying — we must report it and either strengthen D2/D3 or drop the diversity
   claim. The benchmark is designed to permit this outcome.
2. **Cost could dominate.** Truth-gating at ≫ single-agent cost-per-accepted without a matching efficacy
   gain is "correct but not world-class for a working program" — D5 exists to catch this early.
3. **Auth fragility is the recurring substrate failure.** Codex seats have been 401-revoked before;
   the cross-vendor stage degrades loudly (`AUTH_DEGRADED`) rather than faking a pass, but a live
   3-family quorum still depends on interactive re-auth that a headless run cannot perform.
4. **False alarms.** A cross-vendor checker that flags noise is not defensible; the §3 false-alarm-rate
   metric and the regression (no-false-alarm) tasks fence this.
5. **Reward-hacking.** Every automated loop is an optimizer; each needs a stated target + fence +
   instrument + overfit check (LFD). The named live hacks (`orchestrator.py:781`, `compound_judge`
   empty-steps, `injection_clean_boundary`, RapidMeta `cE>cN`) are the fence backlog in `GAP_ANALYSIS.md`.
6. **Position-paper concepts (SGH DAG) are evidence-light.** Adopt the bounded-escalation idea (low
   risk); treat the full DAG rewrite as a measurement-gated bet, never a citation-justified one.

*Every step above is gated by the §3 benchmark as the acceptance test. Until it runs on held-out data,
"world-class" remains a target — which is the honest position.*
