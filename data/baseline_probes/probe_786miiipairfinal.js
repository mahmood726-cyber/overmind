const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
const r = (x, n) => { const p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

const Engine = api.Engine;

// BCG vaccine dataset (raw event/sample counts), RR random-effects DL.
// Same fixture as tests.js test 9; metafor reference logRR ~= -0.7141, tau2 ~= 0.3088.
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
const bcgEff = Engine.calcEffects(bcg, 'binary', 'RR');
const bcgPool = Engine.pool(bcgEff, 'random', 'iv', 'dl', false);
const egg = Engine.eggersTest(bcgEff);

// Hand-worked 2-study continuous MD, fixed, IV (tests.js test 3).
// Expected: es=5.4705882, Q=0.5882353, tau2=0, I2=0.
const mdEff = Engine.calcEffects(
  [{ id: 'A', m1: 10, s1: 2, n1: 10, m2: 5, s2: 2, n2: 10 },
   { id: 'B', m1: 12, s1: 3, n1: 20, m2: 6, s2: 3, n2: 20 }], 'cont', 'MD');
const mdPool = Engine.pool(mdEff, 'fixed', 'iv', 'dl', false);

console.log(JSON.stringify({
  bcg_es: r(bcgPool.es),
  bcg_tau2: r(bcgPool.tau2),
  bcg_Q: r(bcgPool.Q),
  bcg_I2: r(bcgPool.I2),
  bcg_se: r(bcgPool.se),
  bcg_disp: r(bcgPool.displayVal),
  bcg_pval: r(bcgPool.pVal),
  egger_int: r(egg.intercept),
  md_es: r(mdPool.es),
  md_Q: r(mdPool.Q),
  md_lo: r(mdPool.lo),
  md_hi: r(mdPool.hi)
}));
