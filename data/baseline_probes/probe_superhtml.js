const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
const r = (x, n) => { const p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

const Engine = api.Engine;

// BCG vaccine benchmark (binary, RR) -- the exact dataset tests.js validates
// against metafor (pooled logRR ~ -0.7141, tau2 ~ 0.3088).
const bcg = [
  { id: '1', e1: 4, n1: 123, e2: 11, n2: 139 },
  { id: '2', e1: 6, n1: 306, e2: 29, n2: 303 },
  { id: '3', e1: 3, n1: 231, e2: 11, n2: 220 },
  { id: '4', e1: 62, n1: 13598, e2: 248, n2: 12867 },
  { id: '5', e1: 33, n1: 5069, e2: 47, n2: 5808 },
  { id: '6', e1: 180, n1: 1541, e2: 372, n2: 1451 },
  { id: '7', e1: 8, n1: 2545, e2: 10, n2: 629 },
  { id: '8', e1: 505, n1: 88391, e2: 499, n2: 88391 },
  { id: '9', e1: 29, n1: 7499, e2: 45, n2: 7277 },
  { id: '10', e1: 17, n1: 1716, e2: 65, n2: 1617 },
  { id: '11', e1: 186, n1: 50634, e2: 141, n2: 27338 },
  { id: '12', e1: 5, n1: 2498, e2: 3, n2: 2341 },
  { id: '13', e1: 27, n1: 16913, e2: 29, n2: 17854 }
];
const effBcg = Engine.calcEffects(bcg, 'binary', 'RR');
const reBcg = Engine.pool(effBcg, 'random', 'iv', 'dl', false);
const egg = Engine.eggersTest(effBcg);

// Deterministic continuous HKSJ case (hand-worked in tests.js, exact values).
const effHk = Engine.calcEffects(
  [{ id: 'A', m1: 10, s1: 2, n1: 30, m2: 5, s2: 2, n2: 30 },
   { id: 'B', m1: 8, s1: 2, n1: 30, m2: 7, s2: 2, n2: 30 }], 'cont', 'MD');
const reHk = Engine.pool(effHk, 'random', 'iv', 'dl', true);

console.log(JSON.stringify({
  bcg_k: effBcg.length,
  bcg_re_es: r(reBcg.es),
  bcg_re_tau2: r(reBcg.tau2),
  bcg_re_Q: r(reBcg.Q),
  bcg_re_I2: r(reBcg.I2),
  bcg_re_disp: r(reBcg.displayVal),
  bcg_re_lo: r(reBcg.lo),
  bcg_re_hi: r(reBcg.hi),
  bcg_egger_int: r(egg.intercept),
  hk_es: r(reHk.es),
  hk_se: r(reHk.se),
  hk_tau2: r(reHk.tau2)
}));
