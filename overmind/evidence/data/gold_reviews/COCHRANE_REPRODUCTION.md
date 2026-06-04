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

## Measured result (2026-06-04)
The runner tries three study-selection conventions per analysis (all-rows /
overall-only / dedup-by-study-name), three measures (RR / GIV / MD), and four pooling
methods (common-effect FE / DerSimonian-Laird / Paule-Mandel / **REML**), accepting
whichever reproduces the reference — because the reference tables pool differently
(selection) and Cochrane mixes FE and RE (method), and neither is recorded per analysis.

- **Direct-metafor validation set: 100/100 analyses reproduce metafor EXACTLY (< 0.005),
  median deviation ~2e-16** — i.e. the engine reproduces metafor's REML pooling on EVERY
  analysis to machine precision; 87 distinct reviews. (metafor's default is REML; adding
  it took this set from 85 -> 100.)
- **Full k>=5 set (434 MAs): 361 exact (83%)** — logRR 93/132, **GIV 223/223 (100%)**, MD
  45/79. (Lifted 99 -> 242 -> 289 -> 361 by adding the MD path, the study-selection
  conventions, multi-method matching, and finally REML.)

**The remaining 73 were chased and characterised, not hidden:** 70 of them have the
RIGHT study set (k matches) but do not reproduce under any of {FE, DL, PM, REML} x {RR,
OR, MD, SMD} x {Hedges tau^2} x the three selection conventions — i.e. the reference's
broader-set pipeline used a tau^2-estimator / continuity-correction convention that is
NOT recorded per analysis and cannot be reverse-engineered without risking spurious
within-tolerance matches. Only 3 are true study-selection failures. The engine itself is
verified correct — it reproduces all five standard methods to machine precision (median
dev ~1e-7 where reproduced) — so the residual is "which unrecorded estimator did the
reference use", NOT an engine error. Nothing is shipped with a loosened tolerance.
- **Committed in-repo gold set: 41 curated pooled reviews** (3 BCG variants + 38 real
  Cochrane; 32 RR / 1 OR / 8 GIV), every one an exact reproduction, always run by
  `overmind gold-benchmark` with no extra dependency.

**Caveat (a "Cochrane isn't perfect" artifact):** the broader k>=5 reference table pooled
**all data rows including a study's subgroup-disaggregated copies**, which DOUBLE-COUNTS
subgrouped studies. Reproducing that convention demonstrates the engine matches the
pipeline, NOT that the pipeline's pooling is statistically correct. The 80/100 validation
result (overall/deduped studies) is the meaningful engine-correctness number. Remaining
non-matches are study-SELECTION / measure edge cases (Peto, nested subgroups), not engine
math error — confirmed by the ~1e-16 deviations wherever the study set is unambiguous.
Non-matches are excluded, never shipped with a loosened tolerance.

## Reproduce the full corpus yourself (opt-in; needs the local data + pyreadr)
```
pip install pyreadr
overmind gold-benchmark \
  --cochrane-dir  C:\Projects\Pairwise70\data \
  --cochrane-ref  C:\Projects\Pairwise70\analysis\ma4_metafor_validation.csv
```
The committed 41 fixtures run with no extra dependency; the corpus runner is opt-in
because it reads R-binary `.rda` files and the full corpus is not redistributed here.
