const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
const r = (x, n) => { const p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

// metafor dat.bcg log risk ratios (yi) and variances (vi).
// Standard pairwise pooling of log-effects: feed as generic effects (es=yi, se=sqrt(vi)).
var yi = [-0.889311, -1.585389, -1.348073, -1.441551, -0.217547, -0.786116, -1.620898, 0.011952, -0.469418, -1.371345, -0.339359, 0.445913, -0.017314];
var vi = [0.325585, 0.194581, 0.415368, 0.02001, 0.05121, 0.006906, 0.223017, 0.003962, 0.056434, 0.073025, 0.012412, 0.532506, 0.071405];

var bcg = yi.map(function (e, i) {
    return { es: e, vi: vi[i], se: Math.sqrt(vi[i]), excluded: false };
});

// DerSimonian-Laird random-effects pool over dat.bcg.
var tau2 = api.tauDL(bcg.map(function (s) { return Object.assign({}, s); }));
var poolNoH = api.poolIV(bcg.map(function (s) { return Object.assign({}, s); }), tau2, false, 0.95);
var poolH = api.poolIV(bcg.map(function (s) { return Object.assign({}, s); }), tau2, true, 0.95);
var egg = api.eggerTest(bcg.map(function (s) { return Object.assign({}, s); }));

// tests.js hand-worked 3-study generic fixture (DL with heterogeneity).
var g = [
    { es: 0.20, vi: 0.01, se: 0.10, excluded: false },
    { es: 0.50, vi: 0.01, se: 0.10, excluded: false },
    { es: 0.80, vi: 0.04, se: 0.20, excluded: false }
];
var tau2g = api.tauDL(g.map(function (s) { return Object.assign({}, s); }));
var pool3 = api.poolIV(g.map(function (s) { return Object.assign({}, s); }), tau2g, false, 0.95);

console.log(JSON.stringify({
    bcg_es: r(poolNoH.es),
    bcg_tau2: r(tau2),
    bcg_Q: r(poolNoH.Q, 4),
    bcg_I2: r(poolNoH.I2, 3),
    bcg_se: r(poolNoH.se),
    bcg_ciLo: r(poolNoH.ciLo),
    bcg_ciHi: r(poolNoH.ciHi),
    bcg_hksj_se: r(poolH.se),
    bcg_egger_int: r(egg.intercept),
    g3_es: r(pool3.es),
    g3_tau2: r(tau2g),
    g3_I2: r(pool3.I2, 4)
}));
