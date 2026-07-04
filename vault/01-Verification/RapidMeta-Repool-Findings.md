# RapidMeta Re-Pool Findings

**Source report:** `F:\ubcma\verification\2026-07-04-codex-postreauth.md` (SEAT B, WAVE-1 + WAVE-2).
**Method:** Codex (gpt-5.5) independently re-pooled deterministic samples of the RapidMeta dashboards
(`C:\Users\mahmo\rmf-live-fix`), compared to each app's displayed pooled effect, and ran headless-Chrome
(playwright) spot-checks on suspicious apps.

## WAVE-1 — 28-app sample: 16 PASS / 12 FLAG / 0 unparseable
**The math is sound — 27/28 point-estimate + CI agree exactly.** The sample is "not clean" only because of:

1. **1 genuinely wrong output — `MALARIA_VACCINE_REVIEW.html` [P0 display].** The displayed pooled card is
   **blank / non-finite: `RR -- [--]`**, while the embedded data pools to a valid finite RR
   (≈ `0.37 [0.17, 0.82]`). The headline number never rendered — an empty-render / placeholder-leak defect
   (the user sees no pooled effect at all).
2. **Systematic measure-LABEL bug (11 apps) — numbers correct, tag wrong.** Every `*_AUTO_FULL_REVIEW.html`
   continuous-outcome app prints **"RR"** for what are **mean differences**. Codex reproduced the point
   estimate + CI exactly in all 11, so the pooling is right — but several values are *impossible* as risk
   ratios (ARIPIPRAZOLE `-8.70`, ELIGLUSTAT `-30.03`, MIPOMERSEN `-21.35`, DALFAMPRIDINE `6.42`,
   VARENICLINE `2.90`, …). Fix is in the template's measure-label logic (emit MD for continuous).
3. **`IL23_PSA_REVIEW.html` — reconciled to PASS on spot-check** (flagged first as an RR/OR mismatch; the
   playwright check confirmed `Pooled Risk Ratio 1.95 [1.67–2.29]`, k=4). No action.

**Clean passes (16):** ADC_HER2, BTKI_CLL, CART_MM, DOAC_AF, DUPILUMAB_AD, GLP1_CVOT, HF_QUADRUPLE,
HPV_VACCINE, IL23_PSA, JAKI_RA, PEDIATRIC_HIV_ART, POSTPARTUM_HEMORRHAGE, ROTAVIRUS_VACCINE,
SEPSIS_RESUSCITATION, SGLT2_MACE, ZOLBETUXIMAB.

## WAVE-2 — 55 new apps (NMA + DTA + AUTO_FULL): 22 PASS / 33 FLAG
Read truth-first — the 33 flags are **not** 33 wrong numbers. They break down by confidence:

- **(a) The measure-LABEL bug is BROAD (~27 apps), not just continuous.** NMA + auto-review templates
  routinely display the wrong measure label vs the underlying data type, *number matches, label wrong*:
  `EOE_BIOLOGIC_NMA` shows **RR 6.50** but is time-to-event → **HR 6.60**; `HF_QUADRUPLE_NMA` RR 0.82 →
  HR ~0.79; `GASTRIC_FRONTLINE_IO_NMA` RR 0.87 → HR 0.80; `HCC_LOCAL_THERAPY_NMA` RR 0.82 → HR 0.74;
  `OSTEOPOROSIS_BROAD_NMA` RR 0.33 → HR 0.37; `NSCLC_PERIOP_IO_NMA` OR 0.79 → HR 0.74. **The single most
  important RapidMeta defect** — the template's measure-label logic is wrong across binary/continuous/TTE.
- **(b) 2nd blank render — `CTEPH_NMA_REVIEW.html`** shows `OR -- [--]` though data pools to MD ≈ 46.6
  [36.9, 56.3]. Same class as MALARIA.
- **(c) NEW real defect — degenerate thousand-wide CIs** on some continuous auto-reviews (the app itself
  displays them): `LEVOMILNACIPRAN` MD -2.38 **[-5011.96, 5007.21]**, `OBICETRAPIB` **[-7273.71, 7199.54]**,
  `PYROXAMINE`, `SOTAGLIFLOZIN`. A real SE/variance computation defect on certain continuous datasets.
- **(d) LOW-CONFIDENCE — the "26 number-mismatch" count is CONFOUNDED**, do NOT read as 26 wrong apps:
  (1) label-scale artifact (app shows RR, Codex re-pools HR/MD → differ *by definition*); (2) Codex's own
  re-pool blew up on continuous data (`DUTASTERIDE`, `ROMOSOZUMAB` I²100%, …) so for these the **app may be
  right and Codex wrong**. Needs a clean third re-pool to adjudicate.
- **DTA apps — all 6 clean** (COVID_ANTIGEN, DDIMER_PE, GENEXPERT_ULTRA_TB, HSCTN_NSTEMI, MPMRI_PROSTATE,
  PTAU217_AD): Sens/Spec/DOR match Codex's bivariate re-pool.

## Robust conclusions
1. Numeric pooling is **sound** (27/28 exact in wave-1).
2. The **measure-label bug is systematic and broad** (HR/MD/OR shown as RR/OR) — the dominant real defect.
3. **≥2 blank-render apps** (MALARIA, CTEPH) confirm that class.
4. A **real degenerate-CI defect** exists on some continuous apps.
5. The raw "26 number-mismatch" is **not yet trustworthy** — needs a clean re-pool.
6. Only 17 of ~960 dashboards are externally benchmark-validated — the coverage gap that motivates
   [[RapidMeta-QA-SOP]].

## Ties to
[[RapidMeta-QA-SOP]] · [[src-lfd]] (the `cE>cN` at-scale reward-hack class) · [[_Verification-MOC]].
