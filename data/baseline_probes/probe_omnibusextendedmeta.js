const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
const r = (x, n) => { const p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

// --- Block 1: Pooling DL on metadat dat.bcg (log RR + variance) ---
// se = sqrt(vi); w = 1/vi. Standard DL random-effects pool.
const yi = [-0.889311,-1.585389,-1.348073,-1.441551,-0.217547,-0.786116,-1.620898,0.011952,-0.469418,-1.371345,-0.339359,0.445913,-0.017314];
const vi = [0.325585,0.194581,0.415368,0.02001,0.05121,0.006906,0.223017,0.003962,0.056434,0.073025,0.012412,0.532506,0.071405];
const bcgEff = yi.map((te, i) => ({ te: te, se: Math.sqrt(vi[i]), w: 1 / vi[i] }));
const bcg = api.Pooling.pool(bcgEff, 'dl');

// --- Block 2: RVE on tests.js exact inputs (test 9) ---
// IVW mean of te=[0,0.4] with vi=0.04 each, 2 clusters => est 0.2, df=1.
const rve = api.RVE.fit([0, 0.4], [0.04, 0.04], ['c1', 'c2']);

// --- Block 3: Multilevel on tests.js exact inputs (test 10) ---
const ml = api.Multilevel.fit([0.1, 0.3, -0.1, 0.5], [0.05, 0.05, 0.05, 0.05], ['c1', 'c1', 'c2', 'c2']);

// --- Block 4: NMA_RE on tests.js exact inputs (test 8), DL ---
const con = [
  { study: 'S1', t1: 'Plac', t2: 'A', te: 0.5, var: 0.1, cov: 0 },
  { study: 'S2', t1: 'Plac', t2: 'A', te: 0.5, var: 0.1, cov: 0 }
];
const nma = api.NMA_RE.solve(con, ['Plac', 'A'], 'Plac', { method: 'dl' });

// --- Block 5: Matrix op anchor on tests.js exact input (test 7) ---
// A*inv(A) trace should be 3 (identity); dot value D[0][0]=4.
const A = [[2, 1, 1], [1, 3, 2], [1, 0, 0]];
const Ai = api.Matrix.inv(A);
const P = api.Matrix.dot(A, Ai);
const matTrace = P[0][0] + P[1][1] + P[2][2];
const D = api.Matrix.dot([[1, 2, 3], [4, 5, 6]], [[1, 0], [0, 1], [1, 1]]);

console.log(JSON.stringify({
  bcg_est: r(bcg.est),
  bcg_tau2: r(bcg.tau2),
  bcg_Q: r(bcg.Q, 4),
  bcg_i2: r(bcg.i2),
  rve_est: r(rve.est),
  rve_se: r(rve.se),
  ml_est: r(ml.est),
  ml_I2total: r(ml.I2_total, 5),
  nma_A_est: r(nma.est['A'].est),
  nma_A_se: r(nma.est['A'].se),
  nma_tau2: r(nma.tau2),
  mat_trace: r(matTrace),
  mat_D00: r(D[0][0])
}));
