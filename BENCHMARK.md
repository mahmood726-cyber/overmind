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
  + 38 real Cochrane; measures RR/OR/GIV), **worst pooled logRR deviation 3.2e-5**. Each
  fixture pools with the SAME method as its metafor reference (REML/DL), so this is a
  like-for-like check, not a PM-as-proxy approximation. 34/41 are tau^2=0 (FE-degenerate);
  7 are heterogeneous and use REML, exercising the REML tau^2 estimator. Runs with no
  extra dependency. This is the single-config, honest headline.

## 3. Full Cochrane corpus reproduction (opt-in: `--cochrane-dir --cochrane-ref`)
Engine vs metafor over the Pairwise70 corpus (needs `pyreadr`). This is a
**best-of-configurations DIAGNOSTIC** — it credits a match if ANY of up to ~24 (measure x
selection-convention x method) combos lands within tol=0.005, so read as an upper bound:
- **Direct-metafor validation set: 100/100 within tol**, median dev ~2e-16 — but 12/100 are
  ambiguous (>1 distinct estimate within tol), and tol is ~4 orders looser than the engine's
  ~1e-12 floor; the runner reports multiplicity + matched convention (54 all-rows / 45 dedup
  / 1 overall).
- **Full k>=5 set: 361/434 (83%)** — logRR 93/132, GIV 223/223, MD 45/79.

The arc was 99 -> 242 -> 289 -> 361 (MD path -> study-selection conventions -> multi-method
-> REML). See `overmind/evidence/data/gold_reviews/COCHRANE_REPRODUCTION.md` for the full
caveats and the "engine-correctness, NOT Cochrane-correctness" framing (Cochrane MAs are
fragile: ~14.3% reproduction floor, MAFI, HKSJ flips).

## Method coverage (`overmind/evidence/pooling.py`)
FE (common-effect) / DL (DerSimonian-Laird) / PM (Paule-Mandel) / REML (Fisher scoring;
metafor's default). REML reproduces metafor BCG to ~1e-5 (logRR -0.71453 vs -0.71450,
tau2 0.31324 vs 0.31322).

## Benchmark-design reference (foundational)
The harness benchmark (`overmind/benchmark/`, §3 of `harness/WORLD_CLASS_SPEC.md`) is built on the
discipline of **Kapoor, Stroebl, Siegel, Nadgir & Narayanan, "AI Agents That Matter", arXiv:2407.01502
(2024)** — the authoritative reference for agent benchmarking. It prescribes exactly our design:
1. **Jointly optimize COST + ACCURACY, not accuracy alone** — "the cost of running these agents isn't a
   top-line metric reported"; visualize agents on a **cost–accuracy Pareto frontier**. → our
   cost-per-accepted-change (D5) + the affordability gate in the win condition.
2. **Inadequate/absent HOLDOUT sets → agents take shortcuts and overfit** ("many agent benchmarks have
   inadequate holdout sets, and sometimes none at all"); withhold at the right generality level and
   consider keeping it secret. → our **two-slice frozen rule** (AN-2) + sha256 held-out + answer keys
   off the agent surface.
3. **Distinguish model-developer vs downstream-developer** benchmarking needs. → ours is a
   downstream-developer benchmark (does *this* harness catch defects on *our* corpus), not a
   model-capability leaderboard.
4. **Standardization / reproducibility** — release the eval script, report **error bars**, be robust to
   evaluation order. → `scripts/run_benchmark.py` is the released deterministic eval; checkpoint/resume
   makes it order-invariant. (Cross-check adopt-delta: **Wilson confidence intervals** on the rate
   metrics — see `harness/BENCHMARK_RESULTS.md`.)
