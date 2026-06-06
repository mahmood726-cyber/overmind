const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
const r = (x, n) => { const p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

// metafor dat.bcg: log risk ratios (yi) and sampling variances (vi).
const yi = [-0.889311, -1.585389, -1.348073, -1.441551, -0.217547, -0.786116, -1.620898, 0.011952, -0.469418, -1.371345, -0.339359, 0.445913, -0.017314];
const vi = [0.325585, 0.194581, 0.415368, 0.02001, 0.05121, 0.006906, 0.223017, 0.003962, 0.056434, 0.073025, 0.012412, 0.532506, 0.071405];
const bcg = yi.map((y, i) => ({ logOR: y, vi: vi[i] }));
const a = api.poolDL(bcg, { confLevel: 0.95 });

// tests.js heterogeneous two-study case (hand-derived: Q~1.263180, tau2~0.0065795, pOR~0.747749).
const h = api.poolDL([
    { logOR: Math.log(0.7), vi: 0.01 },
    { logOR: Math.log(0.9), vi: 0.04 }
], { confLevel: 0.95 });

console.log(JSON.stringify({
    bcg_k: a.k,
    bcg_est: r(a.pLogOR),
    bcg_tau2: r(a.tau2),
    bcg_Q: r(a.Q, 4),
    bcg_I2: r(a.I2, 3),
    bcg_pSE: r(a.pSE),
    bcg_lci: r(a.lci),
    bcg_uci: r(a.uci),
    het_Q: r(h.Q),
    het_tau2: r(h.tau2),
    het_pOR: r(h.pOR)
}));
