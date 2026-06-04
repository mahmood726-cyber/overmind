<!-- sentinel:skip-file — benchmark snapshot; quotes effect numbers as evidence -->
# Benchmark snapshot (2026-06-04)

Two distinct things are benchmarked: **capability presence** (the self-scored rubric)
and **output correctness** (does the pooling actually reproduce metafor). Keep them
separate — a high presence score is not an accuracy claim.

## 1. Capability-presence self-benchmark (`overmind research-benchmark`)
Rank 1 of 8 comparators. Score depends on the meta-verify state:
- **88.8%** without `--run-meta-verify` (governance/infra weight rebalanced 45% -> 29%
  so a verification harness can't top the table on home-turf weighting alone).
- **97.0%** with `--run-meta-verify` (a CERTIFIED meta-verify maxes the governance and
  continuous-verification dimensions).

Caveats (unchanged, stated honestly): comparator scores are capability-PRESENCE from
public docs, NOT a hands-on head-to-head; the ranking measures coverage, not a measured
output-quality contest. The one dimension that IS measured is `output_correctness` (2.0
weight), fed by the gold benchmark below — fail-closed (0 if the gold set doesn't pass).

## 2. Output-correctness gold benchmark (`overmind gold-benchmark`)
MEASURED reproduction of published / metafor pooled estimates. This is the number that
answers "is the synthesis correct", not "is the capability present".
- **Committed in-repo gold set: 43/43 fixtures pass, 41 pooled reviews** (3 BCG variants
  + 38 real Cochrane; RR/OR/GIV), worst pooled logRR deviation 0.00292. Runs with no
  extra dependency.

## 3. Full Cochrane corpus reproduction (opt-in: `--cochrane-dir --cochrane-ref`)
Engine vs metafor over the Pairwise70 study-level corpus (needs `pyreadr`):
- **Direct-metafor validation set: 100/100 (100%)**, median deviation ~2e-16 — the engine
  reproduces metafor's REML pooling on EVERY analysis to machine precision.
- **Full k>=5 set: 361/434 (83%)** — logRR 93/132, GIV 223/223 (100%), MD 45/79.

The reproduction arc was 99 -> 242 -> 289 -> 361 (MD path -> study-selection conventions
-> multi-method -> REML). See `overmind/evidence/data/gold_reviews/COCHRANE_REPRODUCTION.md`
for the method/selection details and the "engine-correctness, NOT Cochrane-correctness"
framing (Cochrane MAs are fragile: ~14.3% reproduction floor, MAFI, HKSJ flips).

## Method coverage (`overmind/evidence/pooling.py`)
FE (common-effect) / DL (DerSimonian-Laird) / PM (Paule-Mandel) / REML (Fisher scoring;
metafor's default). REML reproduces metafor BCG to ~1e-5 (logRR -0.71453 vs -0.71450,
tau2 0.31324 vs 0.31322).
