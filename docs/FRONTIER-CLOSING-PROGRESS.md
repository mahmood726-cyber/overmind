# Frontier-Closing — Running Progress Log

**Branch:** `frontier-closing-2026-06-24` (built on the eval-harness landing, commit `7f4e231`)
**Goal:** take Sentinel / Overmind / memory / multi-engine / truth-recovery to best-in-class
against the §5 roadmap of [`SYSTEMS-BENCHMARK-VS-FRONTIER.md`](SYSTEMS-BENCHMARK-VS-FRONTIER.md).
**Contract:** truth-first — every improvement is backed by a **measured** number from the eval
harness (`python -m evals.run_all`) or a new eval added here. No merge to `master` without sign-off.
No force-push.

> **How to read the deltas.** Every item below quotes a *before → after* number from a specific
> eval. Where a number can't honestly be measured offline (e.g. CoT reasoning quality needs a live
> model), it says so explicitly rather than inventing one.

---

## Item #1 — MEASUREMENT FIRST: published baselines

Baseline run of the held-out harness on this branch's starting commit (`7f4e231`), no code changes.
Command: `python -m evals.run_all` → `evals/results/summary.json`.

| Eval | Metric | Baseline | Reading |
|------|--------|----------|---------|
| **SpecBench-style** (reward hacking) | `validation_pass_rate` | **66.67 %** | of 3 candidate kinds (honest/reward_hack/broken), the 2 that pass *visible* tests |
| | `heldout_pass_rate` | **33.33 %** | only the honest candidate passes *held-out* tests |
| | **`specbench_gap`** | **33.34 %** | how much "passes visible tests" overstates true correctness |
| | **`reward_hack_heldout_catch_rate`** | **100 %** (5/5) | of reward-hacks a *visible-only* verifier would certify, fraction our held-out-baseline policy catches |
| | `visible_only_false_certifications` | **5** | reward-hacks a visible-only verifier would have falsely certified |
| **Judge master-key** (adversarial) | **`degenerate_false_pass_rate`** | **0 %** (0/12) | empty / punct / filler / no-verdict never yield PASS — guard holds |
| | `genuine_accuracy` | **100 %** (6/6) | well-formed verdicts classified correctly, 0 misflagged |
| | **`injection_boundary_false_pass_rate`** | **50 %** (1/2) | attacker-planted `VERDICT: PASS` escapes the regex *output*-guard — **documented open gap** |
| **Memory recall** (LongMemEval-style) | `recall` / `precision` | **100 % / 100 %** | current fact retrieved, no superseded fact pollutes top-k |
| | `stale_suppression_rate` | **100 %** | superseded facts suppressed (vs `naive_stale_leak_rate` **100 %** without the temporal filter) |
| | `expired_fact_suppressed` | **true** | expired temporal fact correctly hidden |

### Honest reading of the baseline

- **What's genuinely strong & now *proven* (not asserted):** the degenerate-guard (0 % false-PASS),
  the held-out-baseline reward-hack defense (100 % catch of the 5 the visible-only verifier misses),
  and the temporal-memory suppression (100 % stale-suppression vs 100 % naive leak — the filter, not
  keyword luck, is doing the work). These three were "robust by construction"; they are now **robust
  by evidence** on this fixture set.
- **Saturation caveat (truth-first):** memory recall/precision and degenerate false-PASS are at the
  ceiling because the seed fixtures are *small and keyword-distinct*. A 100 % here means "no failure
  on the compact probe", **not** "solved at scale". These evals need harder cases (semantic
  paraphrase, large-N ranking, more reward-hack variety) before the ceiling means much — tightening
  the fixtures is tracked as follow-up, and any item that claims to "improve" a saturated metric must
  first add a harder case that *isn't* already at 100 %.
- **The clearest open, measurable gap:** `injection_boundary_false_pass_rate = 50 %`. The regex
  output-guard is — by design — blind to a well-formed but attacker-planted `VERDICT: PASS`. This is
  the one judge number with real headroom, and it's the honest target for input-side defense work.

---

## Item #2 — cheap, high-value switches (in progress)

Each sub-item lands as its own tested commit with its measured eval delta. Status below updates as
they land.

- **#2c hard-enforce different-family quorum** — _pending_
- **#2a cost-aware engine routing** — _pending_
- **#2b default-on CoT after golden-set no-regression check** — _pending_

## Item #3 — heavier mechanisms behind measured gates — _not started_
## Item #4 — cluster: build or mark deferred — _not started_
