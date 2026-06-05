# Baseline Probe TODO

> Last updated: 2026-04-14 (Batch D scaffolding)
>
> These 13 projects appeared as `numerical SKIP — No baseline file` in the
> 2026-04-13 nightly. Each needs a `probe_<slug>.py` under this directory
> plus a matching `data/baselines/<project_id>.json`. Copy `TEMPLATE.py`
> and fill in per project.

## ⚠ 2026-06-05 path-decay reconciliation (READ BEFORE working this list)

A preflight of the four still-open targets (cbamm, evidence-inference,
fatiha, pairwise70) found the 2026-04-14 paths have decayed — do **not**
fabricate baselines against them:

- **Cbamm** (`#2`) and **Pairwise70** (`#13`): their roots were under
  `C:\Users\user\OneDrive - NHS\Documents\…`. OneDrive roots were removed from
  the scan config (2026-05-04) and these directories are gone on this machine.
  Candidate relocations exist under `C:\Projects` (cbamm-lfa, cbamm-project2,
  CBAMMR, cbammr-bayes; grma/gwam `pairwise70_benchmark_grma`) but their
  canonical identity is ambiguous and **none exposes a deterministic Python
  pooling entrypoint** (verified by grep). Decision needed: which relocation,
  if any, IS the canonical project — or regenerate this list from a fresh
  `overmind scan` instead of chasing slugs.
- **FATIHA** (`#6`): root `C:\Models\FATIHA_Project` is gone; `C:\Models` is not
  a scan root. `C:\Projects\fatiha` exists but has no Python pooling entrypoint
  (it was an R/`Rscript testthat` project; an R-side probe per the section below
  is the only faithful path, and only once the canonical path is reconfirmed).
- **evidence-inference** (`#5`): the path resolves (`C:\Projects\evidence-inference`,
  in scope) BUT its *live* package (`evidence_inference/{models,preprocess,
  experiments}`) is the academic NLP-dataset code with **no meta-analysis pooling
  core**. The pooling helpers live only in `root_backup/` (abandoned). A probe of
  `root_backup` would baseline dead code — out of contract. Needs a live,
  deterministic pooling entrypoint before a numerical baseline is meaningful.

Net: the numerical-SKIP gap should be **re-derived from current discovery**
(scan roots are now `C:\Projects` + `C:\E156` + `C:\Users\mahmo\code`), not
from this decayed slug list. Rows below are preserved as the historical record.

### Fresh-discovery baselines shipped (2026-06-05)

- ✅ **spec-collapse-atlas** (`spec-collapse-atlas-b0a2eceb`, math_score=6, alive
  in `C:\Projects`) — baseline + `probe_spec-collapse-atlas.py` added. Probes the
  pure-Python `spec_collapse.engine` (REML/DL τ² + RE pool) on the canonical
  metadat `dat.bcg` (13-study log-RR) dataset. Values are externally validated
  against metafor by the project's own `ci/check_against_metafor.py` (engine
  matches REML/DL within 2e-3): τ²_REML=0.313243, τ²_DL=0.308758, est=−0.714533,
  pooled var=0.032321. Deterministic (re-run identical); `NumericalWitness.run`
  verified SKIP→PASS; spec registered in `scripts/create_baselines.py`.
- ✅ **overmind** (`overmind-8751d000`, math_score=high) — baselines Overmind's OWN
  pooling engine (`overmind.evidence.pooling.pool`, the gold-benchmark engine) on
  dat.bcg: reproduces metafor EXACTLY (est_log=−0.714533, tau2=0.313243, SE=0.179781).
  Existing spec's stale `C:\overmind` path repaired; tier-logic probe upgraded to
  the pooling cross-check.
- ✅ **metaaudit** (`metaaudit-7da8ccd7`, math_score=high) — baselines
  `metaaudit.recompute.pool_effects_reml` (HKSJ-REML) on dat.bcg: reproduces metafor
  BCG (est=−0.714968, tau2=0.318067, Q/I2 exact). Existing spec's stale `C:\MetaAudit`
  path (in BOTH project_path and the in-probe sys.path) repaired; probe upgraded.
- ✅ **ma-workbench** (`ma-workbench-9e25bb79`) — probes `golden/generate_references.pool`
  on its OWN committed golden dataset G01 and reproduces the committed
  `golden/references/G01-*.json` EXACTLY (pm_estimate=−0.19791392, tau2=0,
  qe=0.07720669). Strongest cross-check: the project ships PM/IV-validated,
  R-cross-checked references.
- ✅ **e156-student-starter** (`e156-student-starter-f1c47832`) — probes
  `tools.pool_pairwise.pool` (Paule-Mandel τ² + HKSJ-floor t CI) on a fixed 5-study
  2×2 set (homogeneous, OR≈0.6 → τ²=0): pooled_or=0.598889, se=0.154654.
- ✅ **hfpef-registry-calibration** (`-8f9669f5`), **trial-truthfulness-atlas**
  (`-d42b956d`), **mission-critical** (`-06fb513a`) — each probes its own DL
  random-effects engine on dat.bcg; all reproduce metafor DL EXACTLY
  (est/mu/log_rr=−0.714117, τ²=0.308758, Q=152.23, I²=92.1).
- ✅ **metasprint-dta** (`-5dffce53`) — DTA bivariate-DL pooling on the BNP-for-HF
  dataset; matches the project's own R/mada `validation_reference.json` within its
  stated tolerances (Sens 0.865/Spec 0.903; I²_spec=73.99 exact).

### Fresh-discovery JS-dashboard baselines shipped (2026-06-05, node probes)

`create_baselines.py` now supports node probes via a per-spec `"lang": "node"`
field (writes `probe_<slug>.js`, runs with an ABSOLUTE quoted node path so the
witness's `split_command` keeps the backslash path — see the create_baseline
comment). A new `--only PREFIX[,PREFIX]` flag builds specs surgically. Node JS
probes `require(path.resolve(process.cwd(), 'engine.js'))` (bare relative require
resolves against the probe file, not cwd). All 4 verified SKIP→PASS via the real
`NumericalWitness` and re-run deterministic:

- ✅ **htmlpairwise-repro** (`-5cbcf684`) — `metaAnalyze(yi,vi)` on dat.bcg
  reproduces metafor EXACTLY (REML τ²=0.313243 est=−0.714533 SE=0.179781;
  DL τ²=0.308758 est=−0.714117; Q=152.2268; I²=92.2211). Strongest cross-check.
- ✅ **html1-effectsize** (`-1d41f3b9`) — effect-size conversions vs closed forms:
  sqrt(3)/π=0.551329, Hedges J=0.992327, d→r=0.371391, atanh(0.5)=0.549306,
  OR→RR=1.818182, Fisher SE(28)=0.2.
- ✅ **html2-tsa** (`-3c1289d5`) — TSA: zα=1.959964, OBF boundary z/√t=2.771808,
  RIS_binary nPerArm=290.4086, all vs closed form.
- ✅ **html3-fragility** (`-06afa9f0`) — fragility index (one-arm, exact Fisher):
  strong(40,60,5,95) FI=21 and border(20,80,9,91) FI=1 match the project's own
  tests.js; main(20,80,6,94) FI=4, p0=0.005427, FQ=0.02.

> ~35 more JS engine.js dashboards remain (C:\Projects, all node-requireable with
> a tests.js). Next batches: betablocker, culpritcontroversy, livingmetacolchicine,
> Metamvhtml, pairwisepro-proportion, Omnibusextendedmeta, html4/5/6, htmlnma-geometry.
> Skip (not in Overmind DB — need a scan first): Eplerenone, Bivariatehtml-,
> Mulitlevelhtmlfinal, neurosynth.

> Remaining Python-engine candidates are not faithful targets: transcendent-ma-lab's
> `pool_quantum` is an explicitly experimental method (no ground truth);
> evidence-forecast loads studies from data (not self-contained); cora/dclnma/lec
> modules are atlas/linkage/absent, not clean pooling. The clean cross-checkable
> harvest (8 baselines) is complete; the rest of the 167 are JS dashboards (node probes).

> NOTE on the wider BASELINE_SPECS list: many pre-existing specs still carry stale
> 2026-04 paths (e.g. `C:\Models\…`, `C:\overmind`). Repair a spec's path (and any
> hardcoded in-probe path) before relying on it; create surgically per spec rather
> than running the whole `create_baselines.py` loop (which would error on the stale
> ones). Most high-math no-baseline projects are JS/HTML dashboards with no Python
> entrypoint — those need a node-based probe, not a Python one.

## Ingredient contract

Before writing a probe, confirm the project:
1. Has a callable entrypoint that does not require network, DB, or
   large data files.
2. Produces output that is deterministic (pin seeds; avoid timestamps).
3. Is currently importable (if it's in `SKIP_PROJECTS` in
   `scripts/nightly_verify.py`, skip until the source is repaired).

## Projects needing probes

| # | Project | Slug | Root | Test command (hint for entrypoint) | Suggested metrics |
|---|---|---|---|---|---|
| 1 | CardioOracle | `cardiooracle` | `C:\Models\CardioOracle` | `python -m pytest tests/test_curation.py -q` | AUC, calibration slope/intercept (Platt), Brier |
| 2 | Cbamm | `cbamm` | `C:\Users\user\OneDrive - NHS\Documents\Cbamm` | `Rscript -e "testthat::test_dir('tests/testthat')"` | pooled RR + tau² (R-side probe; see `probe_metamethods.py` pattern) |
| 3 | Dataextractor | `dataextractor` | `C:\Projects\Dataextractor` | `npm run test` | **node-based probe needed** — call the JS extractor on a fixture PDF, emit field counts |
| 4 | DTA70 | `dta70` | `C:\Users\user\OneDrive - NHS\Documents\DTA70` | `Rscript -e "testthat::test_dir('tests/testthat')"` | bivariate Se/Sp, DOR, HSROC AUC |
| 5 | evidence-inference | `evidence_inference` | `C:\Projects\evidence-inference` | `python -m pytest tests/test_imports.py -q` | key pooled effect + CI; network of interventions if present |
| 6 | FATIHA_Project | `fatiha` | `C:\Models\FATIHA_Project` | `Rscript -e "testthat::test_dir('tests/testthat')"` | publication-bias funnel-asymmetry + adjusted effect |
| 7 | idea12 | `idea12` | `C:\Projects\idea12` | `python -m pytest tests/test_basic.py -q` | netmetareg component effects + transitivity metric |
| 8 | ipd-meta-pro-link | `ipd_meta_pro_link` | `C:\Projects\ipd-meta-pro-link` | `python dev/build-scripts/user_flow_smoke_test.py` | pooled HR + tau² from a fixed small IPD set |
| 9 | metasprint-dose-response | `metasprint_dose_response` | `C:\Projects\metasprint-dose-response` | `python -m pytest test_dose_response_models.py -v` | dose-response curve parameters (slope, inflection) |
| 10 | metasprintnma | `metasprintnma` | `C:\Projects\metasprintnma` | `python test_expanded_suite.py` | NMA edge estimates + SUCRA for a small 4-treatment network |
| 11 | new-app | `new_app` | `C:\Projects\new-app` | `python -m pytest tests/selenium/comprehensive_test.py -q` | **Selenium-only suite** — consider whether a numerical probe makes sense; may be SKIP-permanent |
| 12 | NMA | `nma` | `C:\Projects\NMA` | `Rscript -e "testthat::test_dir('tests/testthat')"` | core NMA pooled log-ratio for fixed network (R-side probe) |
| 13 | Pairwise70 | `pairwise70` | `C:\Users\user\OneDrive - NHS\Documents\Pairwise70` | `python -m pytest tests/selenium_comprehensive_test.py -q` | the 70-MA pairwise Cochrane benchmark already runs RR/OR — probe a single fixed MA from the dataset |

## Already deferred to Batch E (skip until source repaired)

*(empty — all Batch E deferred projects have been repaired as of 2026-04-14)*

## Repaired 2026-04-14 (now awaiting probe + baseline)

- `ipd_qma_project` — 8 syntax errors across `ipd_qma_ml.py`, `ipd_qma_network.py`,
  `ipd_qma_survival.py`, `_ipd_qma_bayesian_scaffold.py` fixed; truncated
  `ipd_qma_ml.py` header reconstructed. Smoke + tests PASS. A probe script
  is still needed to move numerical witness from SKIP to PASS.
- `llm-meta-analysis` — 2 syntax errors (`meta_regression.py` bracket
  mismatch, `report_generator.py` indent) and 3 broken sibling imports
  fixed; backward-compat aliases added to `power_analysis.py`. 40-module
  smoke now PASS (LLM backend adapters skipped via Overmind's
  `_SKIP_FILES` since they need remote APIs).

## R-side probes

For R-based projects (Cbamm, DTA70, FATIHA, NMA), the probe command in
the baseline JSON can point to an Rscript invocation instead of python.
Example baseline:
```json
{
  "command": "Rscript C:/Models/<project>/probe.R",
  "values": {"pooled_logRR": -0.123, "tau2": 0.045},
  "tolerance": 1e-6
}
```
Write `probe.R` inside the project repo (not under `data/baseline_probes/`
which is Python-only convention) and reference it from the baseline JSON.

## Validation checklist before accepting a baseline

- [ ] Probe runs end-to-end with `python <probe>` / `Rscript <probe>`
- [ ] Runs are deterministic (re-run; diff should be empty)
- [ ] Values cross-check against the paper / dashboard when applicable
- [ ] Move probe + baseline into the proper directories and re-run
      `scripts/nightly_verify.py --limit 1 --min-risk high` on just that
      project to confirm numerical witness transitions from SKIP to PASS
