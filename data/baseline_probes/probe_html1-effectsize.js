const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
const r = (x) => Math.round(x * 1e6) / 1e6;
const d = api.logOR_to_d(1.0, null);
const g = api.d_to_g(0.8, null, 50, 50);
const rr = api.d_to_r(0.8, null, 50, 50);
const z = api.r_to_z(0.5, null);
console.log(JSON.stringify({
  logOR1_to_d: r(d.mean),
  sqrt3_over_pi: r(api.constants.SQRT3_OVER_PI),
  d_to_g_J: r(g.J),
  d_to_g_mean: r(g.mean),
  d_to_r: r(rr.mean),
  r05_to_z: r(z.mean),
  OR2_p01_to_RR: r(api.OR_to_RR(2.0, 0.1)),
  fisherSE_28: r(api.fisherSE(28))
}));