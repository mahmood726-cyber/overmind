const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
const r = (x, n) => { const p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

// Fixed literal inputs copied verbatim from the project's tests.js
// (8 studies, one zero-cell). These are the exact values metafor 4.x
// reference numbers in tests.js were generated from.
var labels = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];
var xi = [0, 3, 12, 5, 20, 8, 15, 2];
var ni = [20, 25, 60, 40, 100, 50, 80, 18];
var studies = labels.map(function (L, i) { return { label: L, xi: xi[i], ni: ni[i] }; });

var lo = api.metaProp(studies, { transform: 'logit', level: 0.95 });
var ft = api.metaProp(studies, { transform: 'ft', level: 0.95 });

// Supporting pure functions with fixed literal inputs.
var qn = api.qnorm(0.975);
var isqFt = api.Isq(ft.tau2, ni.map(function (n) { return 1 / (4 * n + 2); }));

console.log(JSON.stringify({
  k: lo.k,
  logit_mu: r(lo.pooled.mu),
  logit_est: r(lo.pooled.est),
  logit_lo: r(lo.pooled.lo),
  logit_hi: r(lo.pooled.hi),
  logit_tau2: r(lo.tau2),
  logit_I2: r(lo.I2),
  logit_Q: r(lo.Q),
  ft_mu: r(ft.pooled.mu),
  ft_est: r(ft.pooled.est),
  ft_lo: r(ft.pooled.lo),
  ft_hi: r(ft.pooled.hi),
  ft_tau2: r(ft.tau2),
  ft_I2: r(ft.I2),
  ft_Q: r(ft.Q),
  qnorm_975: r(qn),
  isq_ft_check: r(isqFt)
}));
