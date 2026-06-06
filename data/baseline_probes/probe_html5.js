const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));

// Deterministic numerical-regression baseline for the DTA engine.
// Datasets are the exact fixtures that tests.js validates, so every
// model below is known to converge and the scalars match the project's
// own hand-derived expected values.

var r = function (x, n) { var p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

// --- Fixture A: 3-study set (tests.js triStats) — validates bivariateModel + calcSROC ---
var triStats = [
  api.calcStudyStats({ tp: 80, fp: 10, fn: 20, tn: 90 }),
  api.calcStudyStats({ tp: 85, fp: 12, fn: 15, tn: 88 }),
  api.calcStudyStats({ tp: 78, fp: 9,  fn: 22, tn: 91 })
];
var bm = api.bivariateModel(triStats);
var sr = api.calcSROC(triStats);

// --- Fixture B: 4-study concordant set (tests.js) — validates thresholdEffectTest (k>=4) ---
var concordant = [
  api.calcStudyStats({ tp: 60, fp: 40, fn: 40, tn: 60 }),
  api.calcStudyStats({ tp: 70, fp: 30, fn: 30, tn: 70 }),
  api.calcStudyStats({ tp: 80, fp: 20, fn: 20, tn: 80 }),
  api.calcStudyStats({ tp: 90, fp: 10, fn: 10, tn: 90 })
];
var th = api.thresholdEffectTest(concordant);

// --- Fixture C: 5-study varied set (tests.js 'five') — validates deeksFunnelTest (k>=5) ---
var five = [
  api.calcStudyStats({ tp: 30,  fp: 20,  fn: 20,  tn: 30 }),
  api.calcStudyStats({ tp: 60,  fp: 40,  fn: 40,  tn: 60 }),
  api.calcStudyStats({ tp: 90,  fp: 60,  fn: 60,  tn: 90 }),
  api.calcStudyStats({ tp: 120, fp: 80,  fn: 80,  tn: 120 }),
  api.calcStudyStats({ tp: 150, fp: 100, fn: 100, tn: 150 })
];
var dk = api.deeksFunnelTest(five);

console.log(JSON.stringify({
  pooled_sens: r(bm.sensitivity.estimate),
  pooled_spec: r(bm.specificity.estimate),
  pooled_dor: r(bm.DOR.estimate),
  sens_tau2: r(bm.sensitivity.tau2),
  spec_tau2: r(bm.specificity.tau2),
  biv_corr: r(bm.correlation),
  sroc_auc: r(sr.auc),
  sroc_qstar: r(sr.qStar),
  sroc_alpha: r(sr.alpha),
  threshold_rho: r(th.rho),
  deeks_slope: r(dk.slope),
  k: bm.k
}));
