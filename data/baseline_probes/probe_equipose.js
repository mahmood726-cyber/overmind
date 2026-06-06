// Deterministic baseline probe for the Equipose / CardioSynth engine.
// Run with cwd = project dir. Prints exactly one JSON line of numeric scalars.
// engine.js exports: probFromLogOR, eggerTest, runREML, buildHistogram.
// Note: runREML is DerSimonian-Laird (not REML); it expects an effect key and
// an SE key (it squares the SE internally to get variance). The metadat bcg
// reference is given as variances (vi), so we feed SE = sqrt(vi).
const path = require('path');
var api = require(path.resolve(process.cwd(), 'engine.js'));
var r = function (x, n) { var p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

// metadat dat.bcg: log risk ratios (yi) and their sampling variances (vi).
var yi = [-0.889311, -1.585389, -1.348073, -1.441551, -0.217547, -0.786116, -1.620898, 0.011952, -0.469418, -1.371345, -0.339359, 0.445913, -0.017314];
var vi = [0.325585, 0.194581, 0.415368, 0.02001, 0.05121, 0.006906, 0.223017, 0.003962, 0.056434, 0.073025, 0.012412, 0.532506, 0.071405];

var bcg = [];
for (var i = 0; i < yi.length; i++) {
  bcg.push({ id: i, e: yi[i], s: Math.sqrt(vi[i]) });
}

var pooled = api.runREML(bcg, 'e', 's');
var egg = api.eggerTest(bcg, 'e', 's');

// Egger on a perfectly symmetric funnel (tests.js: constant effect -> intercept = mean(y)).
var eggSym = api.eggerTest(
  [{ e: -0.20, s: 0.05 }, { e: -0.20, s: 0.10 }, { e: -0.20, s: 0.20 }], 'e', 's');

// tests.js hand-worked 2-study DL pooling reference values.
var two = api.runREML(
  [{ id: 'A', e: -0.16, s: 0.06 }, { id: 'B', e: -0.21, s: 0.05 }], 'e', 's');

// tests.js heterogeneous 2-study reference (tau2=0.17, I2=94.4444).
var het = api.runREML(
  [{ id: 'A', e: -0.50, s: 0.10 }, { id: 'B', e: 0.10, s: 0.10 }], 'e', 's');

// probFromLogOR fixed values from tests.js.
var prob0 = api.probFromLogOR(0.04, 0);
var probHalf = api.probFromLogOR(0.04, Math.log(0.5));

// Deterministic histogram: uniformly spread sorted array, 20 bins (no sampling).
var sorted = [];
for (var j = 0; j < 1000; j++) { sorted.push(j / 1000); }
var hist = api.buildHistogram(sorted, 20);
var histSum = 0;
for (var h = 0; h < hist.length; h++) { histSum += hist[h].y; }

console.log(JSON.stringify({
  bcg_mu: r(pooled.mu),
  bcg_se_pool: r(pooled.se_pool),
  bcg_tau2: r(pooled.tau2),
  bcg_I2: r(pooled.I2),
  bcg_pred_lo: r(pooled.pred_lo),
  bcg_pred_hi: r(pooled.pred_hi),
  bcg_egger_intercept: r(egg.intercept),
  egger_sym_intercept: r(eggSym.intercept),
  two_mu: r(two.mu),
  two_se_pool: r(two.se_pool),
  het_tau2: r(het.tau2),
  het_I2: r(het.I2),
  prob_zero: r(prob0),
  prob_half: r(probHalf),
  hist_bins: r(hist.length),
  hist_sum: r(histSum)
}));
