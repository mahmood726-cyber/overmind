const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));

const r = (x, n) => { const p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

// Fixed inputs taken verbatim from tests.js (metafor REML anchor dataset).
const yi = [0.00, 0.52, -0.30, 0.81, 0.18, 0.95, -0.12, 0.60, 0.35, 0.05];
const vi = [0.02, 0.03, 0.015, 0.04, 0.02, 0.05, 0.018, 0.03, 0.025, 0.012];

// Vague-prior configuration used by the anchor test in tests.js.
const res = api.bayesMA(yi, vi, { scale: 5.0, level: 0.95, nTau: 800, nMu: 800 });

// Pure closed-form anchors.
const dnorm0 = api.dnorm(0, 0, 1);                 // 1/sqrt(2*pi) = 0.398942
const grid = api.linspace(-8, 8, 2001);
const dn = grid.map(function (x) { return api.dnorm(x, 0, 1); });
const trapzN01 = api.trapz(grid, dn);              // ~1
const hc = api.halfCauchy(0, 0.5);                 // (2/pi)/0.5
const fe = api.fitAtTau(yi, vi, 0).muHat;          // fixed-effect (tau=0) mean

console.log(JSON.stringify({
  muMean: r(res.mu.mean, 5),
  muMedian: r(res.mu.median, 5),
  muCrILo: r(res.mu.crI.lo, 5),
  muCrIHi: r(res.mu.crI.hi, 5),
  predMean: r(res.pred.mean, 5),
  predCrILo: r(res.pred.crI.lo, 5),
  predCrIHi: r(res.pred.crI.hi, 5),
  tauMean: r(res.tauSummary.mean, 5),
  tauMedian: r(res.tauSummary.median, 5),
  muHatFE: r(res.muHatFE, 6),
  fitFEMuHat: r(fe, 6),
  dnorm0: r(dnorm0, 6),
  trapzN01: r(trapzN01, 6),
  halfCauchy0: r(hc, 6),
  k: res.k,
  noError: res.error ? 0 : 1
}));
