// Deterministic baseline probe for C:/Projects/Omniinfoloss1/engine.js
// For Overmind NumericalWitness. Prints exactly one line of JSON of stable
// numeric scalars across several engine modules (a numerical regression baseline).
// Cross-checks:
//   bcg* : metafor metadat dat.bcg log-RR DL random-effects (est=-0.714117,
//          tau2=0.308758, Q=152.2268, I2=92.117) and the HKSJ pooled SE.
//   p2*  : tests.js hand-worked 2-study DL pool (est=0.5, tau2=0.25, Q=2, i2=0.5).
//   mat* : tests.js Matrix sanity inv([[2,0],[0,4]]) and A*Ainv=I.
//   info*: tests.js InfoMetrics base-only (traditional=2/17*100, gain=3.5).
//   rve* : RVE cluster-sandwich on a fixed 6-effect / 4-cluster fixture.
//   ml*  : Multilevel 3-level GLS fit on the same fixed fixture (I2_total).
//   nma* : NMA_RE DL solve on a fixed 4-contrast / 3-treatment network.
// No Date, no Math.random, no file reads; all inputs are literal.

var path = require('path');
var api = require(path.resolve(process.cwd(), 'engine.js'));
var r = function (x, n) { var p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

// --- dat.bcg log-RR effects (yi, vi from metafor metadat) ---
var yi = [-0.889311, -1.585389, -1.348073, -1.441551, -0.217547, -0.786116, -1.620898, 0.011952, -0.469418, -1.371345, -0.339359, 0.445913, -0.017314];
var vi = [0.325585, 0.194581, 0.415368, 0.02001, 0.05121, 0.006906, 0.223017, 0.003962, 0.056434, 0.073025, 0.012412, 0.532506, 0.071405];
var eff = yi.map(function (t, i) { return { te: t, se: Math.sqrt(vi[i]), w: 1 / vi[i] }; });
var bcgDL = api.Pooling.pool(eff, 'dl');
var bcgHK = api.Pooling.pool(eff, 'hk');

// --- tests.js 2-study DL pool: te=[0,1], se=[0.5,0.5] ---
var p2 = api.Pooling.pool([{ te: 0, se: 0.5, w: 4 }, { te: 1, se: 0.5, w: 4 }], 'dl');

// --- tests.js Matrix anchor ---
var Ai = api.Matrix.inv([[2, 0], [0, 4]]);
var I = api.Matrix.dot([[2, 0], [0, 4]], Ai);

// --- tests.js InfoMetrics base-only ---
var info = api.InfoMetrics.calculate([{ hasDist: false, hasBase: true }]);

// --- fixed RVE / Multilevel fixture: 6 effects, 4 clusters ---
var Y = [0.1, 0.3, -0.2, 0.5, 0.0, 0.4];
var V = [0.04, 0.05, 0.06, 0.03, 0.07, 0.02];
var cl = [1, 1, 2, 2, 3, 4];
var rve = api.RVE.fit(Y, V, cl);
var ml = api.Multilevel.fit(Y, V, cl);

// --- fixed NMA_RE network: 4 contrasts, treatments A(ref)/B/C ---
var con = [
  { study: 's1', t1: 'A', t2: 'B', te: 0.5, var: 0.05 },
  { study: 's2', t1: 'A', t2: 'C', te: 0.8, var: 0.06 },
  { study: 's3', t1: 'B', t2: 'C', te: 0.2, var: 0.04 },
  { study: 's4', t1: 'A', t2: 'B', te: 0.6, var: 0.05 }
];
var nma = api.NMA_RE.solve(con, ['A', 'B', 'C'], 'A', { method: 'dl' });

console.log(JSON.stringify({
  bcg_est: r(bcgDL.est),
  bcg_tau2: r(bcgDL.tau2),
  bcg_Q: r(bcgDL.Q),
  bcg_i2: r(bcgDL.i2 * 100),
  bcg_hk_se: r(bcgHK.se),
  p2_est: r(p2.est),
  p2_tau2: r(p2.tau2),
  mat_inv11: r(Ai[1][1]),
  mat_I_diag: r(I[0][0] + I[1][1]),
  info_gain: r(info.relativeGain),
  rve_se: r(rve.se),
  ml_I2tot: r(ml.I2_total),
  nma_B: r(nma.est.B.est),
  nma_C: r(nma.est.C.est)
}));
