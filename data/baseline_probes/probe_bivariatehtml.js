// Deterministic baseline probe for Bivariatehtml- engine.js (Overmind NumericalWitness).
// Uses ONLY non-RNG entry points: metaAnalysis (DL), remlTau2, pauleMandel,
// conformalPrediction, transportabilityAnalysis. Inputs are the EXACT fixed
// datasets tests.js hand-derives, which are known to converge.
var path = require('path');
var api = require(path.resolve(process.cwd(), 'engine.js'));
var r = function (x, n) { var p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

// Two-trial DL example tests.js derives by hand:
//   A: logHR=ln(0.5), SE=0.1 ; B: logHR=ln(0.8), SE=0.2
// Expected: Q=4.41807, tau2=0.0854517, I2=77.3657, mu=-0.490060, se=0.232825.
var twoTrials = [
  { logHR_benefit: Math.log(0.5), SE_benefit: 0.1 },
  { logHR_benefit: Math.log(0.8), SE_benefit: 0.2 }
];
var dl = api.metaAnalysis(twoTrials, function (t) { return t.logHR_benefit; }, function (t) { return t.SE_benefit; }, 'DL');

// Bundled 4-trial benefit data: REML default estimator, PM, DL (tests.js: PM<=REML<=DL).
var T = api.TRIALS;
var yB = T.map(function (t) { return t.logHR_benefit; });
var vB = T.map(function (t) { return t.SE_benefit * t.SE_benefit; });
var remlB = api.remlTau2(yB, vB, T.length);
var pmB = api.pauleMandel(yB, vB, T.length);
var dlBfull = api.metaAnalysis(T, function (t) { return t.logHR_benefit; }, function (t) { return t.SE_benefit; }, 'DL');

// Deterministic chi-square quantiles (R-validated in tests.js).
var qchisq_975_3 = api.chiSquareQuantile(0.975, 3);
var qchisq_025_3 = api.chiSquareQuantile(0.025, 3);

// Conformal prediction (pure linear algebra, no RNG) on bundled trials.
var reB = api.metaAnalysis(T, function (t) { return t.logHR_benefit; }, function (t) { return t.SE_benefit; }, 'DL');
var reH = api.metaAnalysis(T, function (t) { return t.logHR_harm; }, function (t) { return t.SE_harm; }, 'DL');
var conf = api.conformalPrediction(T, reB, reH);
var confDet = conf.cov.var_B * conf.cov.var_H - conf.cov.cov_BH * conf.cov.cov_BH;

// Transportability (deterministic SMD grid).
var trans = api.transportabilityAnalysis();

console.log(JSON.stringify({
  dl_Q: r(dl.Q),
  dl_tau2: r(dl.tau2),
  dl_I2: r(dl.I2),
  dl_mu: r(dl.mu),
  dl_se: r(dl.se),
  reml_tau2: r(remlB),
  pm_tau2: r(pmB),
  dlfull_tau2: r(dlBfull.tau2),
  qchisq_975_3: r(qchisq_975_3),
  qchisq_025_3: r(qchisq_025_3),
  conf_det: r(confDet),
  trans_aggSMD0: r(trans[0].aggSMD)
}));
