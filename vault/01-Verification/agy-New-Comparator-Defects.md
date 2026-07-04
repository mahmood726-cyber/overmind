# agy — New Comparator Defects (third-vendor bug review)

**Source report:** `F:\ubcma\verification\2026-07-04-agy-thirdvendor.md` (JOB 2).
**Vendor:** Antigravity `agy` v1.0.16 (pc1, authenticated), run as an independent THIRD vendor. Each
finding below was **independently re-checked in code by Claude** and tagged NEW / OVERLAP / DIVERGENCE.

## 2 genuinely NEW confirmed defects (Codex did NOT flag) — all comparator/diagnostic-level
1. **`comparators.py` `quality_effects` (~L262) — omits the IVhet heterogeneity variance.** Labeled
   "Doi et al. 2015, IVhet-based" but returns `se = sqrt(1/Σw)` (naive inverse-variance FE variance); never
   computes τ² nor the IVhet quasi-variance `Σ (w_i/Σw)²(s_i²+τ²)`. Under heterogeneity the SE is
   underestimated / CI too narrow. **CONFIRMED real.** Codex did not review `quality_effects`. Comparator
   column only — not in the AdaptShrink default panel → **no shipped number affected.**
2. **`field_learned.py:181 predict_loo` + `:303 score` — observation-noise double-count.** `predict_loo`
   returns `sd = sqrt(1/diag(Kinv))`, the LOO predictive SD of the *observed* value (K already carries
   `se_i²` on its diagonal); `score` then forms `hw = z*sqrt(sd² + se_t²)`, adding `se_t²` a **second
   time**. Over-widens raw LOO/k-fold coverage-width **diagnostics**; does NOT touch the MAE-based "beats
   within-MA" headline (point estimate `mu` only) and is largely absorbed by the conformal recalibration.
   **CONFIRMED real.**

## Deeper-than-Codex — Copas objective mis-spec (PLAUSIBLE, comparator-only)
On the already-fixed Copas ([[P0-P1-Bug-Fixes]]), agy says the **objective is still mis-specified**:
`comparators.py:181` does `ll += np.sum(np.log(Phi_u))` (adds `+logΦ(u)`), whereas the exact Copas–Shi
(2000) observed-data log-likelihood *subtracts* `logΦ(u_i)` and adds `logΦ(v_i)`, while the y-density
already uses selection-adjusted moments. So it is a hybrid with the wrong sign on the `logΦ(u)` term,
biasing the optimum toward selection-off → **under-corrects**. Claude **structurally confirmed** the code
fact. Caveat: agy's "still returns the naive pool" is an over-statement — the Claude fix *does* move the
estimate (−0.074→−0.085), so it under-corrects rather than fully collapsing. **AdaptShrink excludes Copas →
no headline affected.**

## Overlap with Codex (independent re-discovery — corroborates)
- **`aact_kappa.py:127,129` truthiness guard drops legitimate 0.0** + **`:110` non-comparable subset
  mixing** (`mean_amd` over all trials vs `mean_z` over SE-valid subset). → **OVERLAP** with Codex P2 #6,
  independently found. Confirmed real, low real-data impact, disclosed; the frozen deploy path
  (`aact_kappa_freeze.py`) is unaffected.

## Divergence adjudicated AGAINST agy
- **`trim_and_fill` FE-se:** agy called the fixed-effect variance formula a bug; Claude sides with Codex —
  the *entire* estimator pools with FE weights, so it is an internally-consistent FIXED-effect Duval–Tweedie
  estimator (the original form), **not** a defect. Not counted.

## Over-statements flagged (truth-first)
agy wrote `knapp_hartung` raises a `ZeroDivisionError` at k=1 — the real mechanism is a NaN via `df=0` /
numpy inf (HKSJ/PI are undefined for k<2 by construction). Low priority, out-of-contract. And its Copas
"naive pool" phrasing over-states (see above).

## Bottom line
agy is a **genuine third perspective**: it corroborated where Codex was right, went deeper on Copas, and
found 2 new comparator-level defects Codex missed — **none of which touch the transport-NMA headline or the
"beats within-MA" MAE headline.** No fabricated agreement: every agy number was independently re-checked
by Claude.

## Ties to
[[Triple-Vendor-Transport-NMA-Witness]] · [[P0-P1-Bug-Fixes]] · [[Cross-Vendor-Witness-SOP]] ·
[[_Verification-MOC]].
