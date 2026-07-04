# SOP — RapidMeta QA (dashboard re-pool + display audit)

> **Version:** v1.0 · **Status:** exercised 2026-07-04 (28-app + 55-app samples) · **Owner:** RapidMeta
> **Change log:** v1.0 — codified from the WAVE-1/WAVE-2 Codex re-pool findings.

## Purpose
Independently re-pool a sample of the ~960 RapidMeta dashboards and audit both the **numbers** and the
**displayed labels/render** — closing the gap that only 17 of ~960 are externally benchmark-validated.

## When to use
After any batch of dashboard generation/fixes; as a standing scheduled lane. Maker generates; a
**different vendor** re-pools ([[Cross-Vendor-Witness-SOP]]).

## Procedure
1. **Deterministic sample.** Pick a fixed (seeded) N-app sample from the live tree (`rmf-live-fix`), so the
   run is reproducible. Exclude apps already covered by prior waves to widen coverage.
2. **Independent re-pool.** Recompute each app's pooled effect (inverse-variance / PM / bivariate for DTA)
   from the *embedded data*, not the displayed card.
3. **Compare on THREE axes — do not collapse them:**
   - **Number:** does the point estimate + CI match? (today: 27/28 exact in wave-1.)
   - **Label:** is the measure tag correct for the data type? (the dominant defect: MD/HR/OR shown as
     "RR"/"OR" across ~27 apps — *number right, tag wrong*.)
   - **Render:** did the card render a finite value at all? (blank `RR -- [--]` = MALARIA, CTEPH.)
4. **Playwright spot-check** the suspicious apps before finalizing (reconciles false flags — e.g. IL23_PSA
   cleared to PASS).
5. **Separate real defects from confounds.** A "number mismatch" is **not** a wrong app when it is really
   the label-scale artifact (app shows RR, re-pool shows HR/MD) or the checker's *own* unstable continuous
   re-pool (I²100%, thousand-wide CIs). Flag these LOW-CONFIDENCE and require a clean third re-pool.

## Objective gate / fences (LFD)
- **Denominator fence:** `events ≤ N` per 2×2 cell — the `cE>cN` class (e.g. `CAPLACIZUMAB_TTP cE=524 >
  cN=39`) is the at-scale reward-hack ([[src-lfd]]); a "found nothing" run **must FAIL a planted
  `cE>cN` canary** or the checker is broken.
- **R-parity / benchmark-regression** gate on the validated subset.

## Stop conditions
- **Success:** N validate in a row (Loop Library "quality streak" — *"after N successful cases in a row"*).
- **Failure:** after K unrecoverable retries → `TASK_FAILED:[reason]`.
- Cap **both** iterations and $ (see [[swipe-file]] spec (a)).

## Known defect classes (2026-07-04)
1. Systematic **measure-LABEL** bug (broad: binary/continuous/TTE) — template label logic. **Top priority.**
2. **Blank render** / placeholder-leak (≥2 apps).
3. **Degenerate CI** (variance blow-up) on some continuous datasets.
4. Confounded "number-mismatch" count — needs clean re-pool.

## Ties to
[[RapidMeta-Repool-Findings]] · [[src-loop-library]] (quality-streak loop) · [[src-lfd]] (canary/fence) ·
[[_SOPs-MOC]].
