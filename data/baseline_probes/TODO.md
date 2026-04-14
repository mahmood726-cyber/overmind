# Baseline Probe TODO

> Last updated: 2026-04-14 (Batch D scaffolding)
>
> These 13 projects appeared as `numerical SKIP — No baseline file` in the
> 2026-04-13 nightly. Each needs a `probe_<slug>.py` under this directory
> plus a matching `data/baselines/<project_id>.json`. Copy `TEMPLATE.py`
> and fill in per project.

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

- `ipd_qma_project` — cascading syntax errors in `ipd_qma_ml.py`, `ipd_qma_network.py`, `ipd_qma_survival.py`
- `llm-meta-analysis` — compounding package-layout / dataclass-ordering issues

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
