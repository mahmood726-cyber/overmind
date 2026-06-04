<!-- sentinel:skip-file — measured-result report; quotes effect numbers as evidence -->
# Cochrane corpus reproduction — what it proves (and what it does NOT)

## What this measures
The pooling engine (`overmind/evidence/pooling.py`) reproduces **metafor's** pooled
estimate on real Cochrane meta-analysis data. The substrate is the Pairwise70
study-level corpus (595 Cochrane reviews, `*_data.rda`), with metafor's pooled
values as the reference (`ma4_metafor_validation.csv`).

## What this does NOT prove — "Cochrane itself is not perfect"
Reproducing metafor validates the **engine's pooling math**, given the same study
data and method. It does **NOT** certify that the underlying Cochrane reviews are
correct. Cochrane meta-analyses are themselves fragile:
- The Pairwise70 family's central finding is a **reproduction floor of ~14.3%** (by
  outcome: 12.9% / 25.0% / 27.0%).
- The **Meta-Analysis Fragility Index** (MAFI) shows how few event reassignments flip
  a pooled significance verdict.
- Conclusions flip under **HKSJ** vs standard variance (the `conclusion_changed`
  signal in `ma_verify.py`).

So the gold benchmark is an **engine-correctness** check on a real-data substrate —
not a claim that any review's conclusion is right. The engine already carries the
tools to surface the fragility (`hksj_se` in `pool()`, the HKSJ-floor rule, and
`ma_verify`'s conclusion-instability check).

## Measured result (2026-06-05)

### Committed, always-run gold set (no dependency) — the honest headline
- **41 committed pooled fixtures, 43/43 pass, worst pooled logRR deviation 3.2e-5.** 3 BCG
  variants + 38 real Cochrane; **measures 32 RR / 1 OR / 8 GIV** (MD/SMD are NOT in the
  committed set — they are exercised only in the opt-in corpus run below).
- Each fixture now pools with the SAME method as its metafor reference (REML for the RR/GIV
  reviews whose reference is metafor-REML; DL for the BCG-OR fixture, whose committed value
  is the DL OR estimate), so the gated `estimate_log` is a like-for-like check, not a
  PM-as-proxy-for-REML approximation absorbed by a loose tolerance.
- **Heterogeneity disclosure (so "reproduces REML" is not over-read):** 34 of the 41
  fixtures pool to tau^2=0, where FE/DL/PM/REML all collapse to the identical fixed-effect
  estimate — those validate the FE path only. **7 fixtures are genuinely heterogeneous
  (tau^2>0)** and now use REML, so the REML tau^2 estimator IS exercised by their gated
  estimate_log; the BCG-RR fixture additionally gates tau^2/I^2 against the documented
  metafor values. (The 4 heterogeneous Cochrane fixtures have no independent metafor
  tau^2/I^2 source offline, so tau^2/I^2 are not separately gated on them — only the
  REML-dependent estimate_log is.)

### Opt-in full-corpus run — a best-of-configurations DIAGNOSTIC, not a single-pipeline rate
The runner tries, per analysis, three study-selection conventions (all-rows / overall-only
/ dedup-by-study-name) x three measures (RR / GIV / MD) x four methods (FE / DL / PM / REML)
and credits a reproduction if ANY combination lands within tol=0.005 — because neither the
reference's study selection nor its tau^2 method is recorded per analysis. This is a
*best-of-up-to-24-configurations* search, so read these as upper-bound diagnostics, not a
fidelity-to-the-intended-config measurement:
- **Direct-metafor validation set: 100/100 within tol** (median dev ~2e-16). Caveat: in
  **12/100** analyses more than one distinct estimate lands within tol (multiplicity>1), so
  the credit goes to whichever combo matched, not necessarily the reference's config; and
  tol=0.005 is ~4 orders of magnitude looser than the engine's ~1e-12 reproduction floor.
  The runner now reports per-analysis multiplicity and the matched convention/method.
- **Full k>=5 set (434 MAs): 361 within tol (83%)** — logRR 93/132, GIV 223/223, MD 45/79.

**The remaining 73:** 70 have the RIGHT study set (k matches) but do not reproduce under
the runner's {FE,DL,PM,REML} x {RR,GIV,MD} x three-convention search (I also separately
probed OR, SMD, and a Hedges tau^2 estimator in throwaway scripts — none recovered them;
those measures/estimators are NOT in the shipped runner). Only 3 are true study-selection
failures. The five standard methods reproduce metafor to machine precision on every
*checkable* analysis, so the most parsimonious explanation for the 70 is an unrecorded
reference estimator/continuity convention — but those 70 are **unverified, not
confirmed-correct**: by construction you cannot distinguish an unrecorded-convention
mismatch from a genuine bug in a case you cannot reproduce. They are excluded from the
shipped gold set, never shipped with a loosened tolerance.

**A "Cochrane isn't perfect" artifact:** the broader k>=5 reference table pools **all data
rows including a study's subgroup-disaggregated copies**, which DOUBLE-COUNTS subgrouped
studies. Reproducing that convention shows the engine matches the *pipeline*, not that the
pipeline's pooling is statistically correct.

## Reproduce the full corpus yourself (opt-in; needs the local data + pyreadr)
```
pip install pyreadr
overmind gold-benchmark \
  --cochrane-dir  C:\Projects\Pairwise70\data \
  --cochrane-ref  C:\Projects\Pairwise70\analysis\ma4_metafor_validation.csv
```
The committed 41 fixtures run with no extra dependency; the corpus runner is opt-in
because it reads R-binary `.rda` files and the full corpus is not redistributed here.
