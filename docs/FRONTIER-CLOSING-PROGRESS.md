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

### #2c — hard-enforce different-family quorum panels ✅ landed

Was **warn-only**: a `claude,codex,codex-noreen` panel ran as a "3-judge" quorum, flagged but live,
advertising ~2.25 effective votes as if 3. Now **hard-enforced** by default
(`OVERMIND_JUDGE_QUORUM_ENFORCE=1`, escape hatch `0/off/warn`): `build_judge` repairs a correlated
panel by dropping same-family redundancy (one judge per family), and if **<2 families** remain it is
not a real quorum, so it falls back to a single-engine chain instead of advertising false
independence.

New eval `evals/quorum_decorrelation.py` (now in `run_all`), run against the **real** `build_judge`:

| Metric | Before (warn-only) | After (enforced) |
|--------|--------------------|------------------|
| **correlated-panel overcount rate** | **100 %** (5/5) | **0 %** (0/5) |
| honest-panel unchanged rate (no-regression) | 100 % (3/3) | 100 % (3/3) |

"Overcount" = a panel that runs as a `QuorumJudge` whose `effective_votes < nominal_votes`. After
enforcement every surviving quorum has `effective_votes == nominal_votes` (all distinct families);
the rest correctly fall back. Honest (all-distinct) panels are provably untouched.

**Honest scope:** the effective-vote estimate is a heuristic (0.25/redundant-judge), not a calibrated
independence measure — enforcement makes the *structural* guarantee "no surviving quorum spans a
duplicate family", which is exact; it does not claim the surviving panel's votes are perfectly
independent. Tests: `tests/unit/test_judge_factory.py` (8 new) + `test_evals_harness.py` (1 new).

### #2a — cost-aware engine routing (local-first, escalate on uncertainty) ✅ landed

New `RoutedJudge` + `OVERMIND_JUDGE_MODE=routed` (`build_judge`, first engine = cheap tier, rest =
expensive escalation tier — a cross-family quorum if >1, else a single engine). Runs the cheap/local
judge first and **escalates to the expensive quorum only when the cheap verdict is untrustworthy**.
Truth-first asymmetry (a false PASS is the costly error): never trust a cheap `judge_error` /
`judge_degenerate`; accept a cheap verdict only above `escalate_below=0.75`; and require a cheap
**PASS** to additionally clear a higher `pass_floor=0.85`. Returned verdict carries
`routed_cheap_accepted` / `routed_escalated` so the path is auditable.

New eval `evals/engine_routing.py` (in `run_all`), against the **real** `RoutedJudge`:

| Metric | Always-expensive | Routed |
|--------|------------------|--------|
| **expensive (quorum) invocation rate** | **100 %** | **50 %** (= escalation rate) |
| accuracy | 100 % | **100 %** (`routed_preserves_expensive=True`) |
| cheap-only accuracy (counterfactual) | — | **62 %** |

The headline (quorum-invocation rate **100 % → 50 %**) is **assumption-free** — it directly halves the
expensive-tier call volume, which is the token-cost lever. Routing loses **zero** accuracy vs running
the quorum every time, while naive "just use local" would drop to 62 %. A secondary token-saving
figure (25 % at a conservative 4:1 expensive:cheap ratio) is reported *with its ratio stated* — the
real saving scales with the true local:quorum cost ratio, so we lead with the invocation rate, not
the dollar number.

**Honest scope:** the eval uses scripted cheap/expensive verdicts (deterministic, offline) — it
proves the *routing logic* cuts invocations without losing accuracy on a labelled set; it does not
measure a live local model's real confidence calibration (that needs an online run). Tests:
`tests/unit/test_judge_factory.py` (+5) + `test_evals_harness.py` (+1).

- **#2b default-on CoT after golden-set no-regression check** — _pending_

## Item #3 — heavier mechanisms behind measured gates — _not started_
## Item #4 — cluster: build or mark deferred — _not started_
