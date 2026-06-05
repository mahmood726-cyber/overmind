const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
const r = (x, n) => { const p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };
const rb = api.risBinary(0.3, 0.2, 0.05, 0.8, true);
const rc = api.risContinuous(1.0, 0.5, 0.05, 0.8, true);
console.log(JSON.stringify({
  zAlpha_0975: r(api.zAlpha(0.05, true)),
  zBeta_08: r(api.zBeta(0.8)),
  obf_t05: r(api.obfBoundary(0.5, 0.05, true)),
  ris_binary_nPerArm: r(rb.nPerArm, 4),
  ris_binary_total: r(rb.ris, 4),
  ris_continuous_nPerArm: r(rc.nPerArm, 4),
  adj_factor_D05: r(api.adjustmentFactor(0.5)),
  adjusted_ris: r(api.adjustedRIS(100, 0.5), 4)
}));