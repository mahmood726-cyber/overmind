const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
const r = (x, n) => { const p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

const Engine = api.Engine;
const Matrix = api.Matrix;

// --- Matrix-op anchor: inverse of a fixed 2x2 (det = -6). ---
// A = [[4,3],[6,3]] -> A^-1 = [[-0.5, 0.5],[1, -0.6666667]]
const Ainv = Matrix.inv([[4, 3], [6, 3]]);
const ident = Matrix.dot(Ainv, [[4, 3], [6, 3]]);

// --- Fixed-effect MD pooling (2 effects, 1 cluster). ---
const mdEff = Engine.calcEffects(
    [{ id: 'A', m1: 10, s1: 2, n1: 10, m2: 5, s2: 2, n2: 10 },
     { id: 'A', m1: 12, s1: 3, n1: 20, m2: 6, s2: 3, n2: 20 }], 'cont', 'MD');
const mdFixed = Engine.pool(mdEff, 'fixed', null, null, null);

// --- Log-scale OR pooling, two identical effects in two clusters. ---
const orEff = Engine.calcEffects(
    [{ id: '1', e1: 10, n1: 100, e2: 20, n2: 100 },
     { id: '2', e1: 10, n1: 100, e2: 20, n2: 100 }], 'binary', 'OR');
const orPool = Engine.pool(orEff, 'random', null, null, null);

// --- True multilevel structure: 3 studies / 4 effects, random effects. ---
const mlEff = Engine.calcEffects(
    [{ id: 'S1', m1: 10, s1: 2, n1: 30, m2: 5, s2: 2, n2: 30 },
     { id: 'S1', m1: 11, s1: 2, n1: 30, m2: 5, s2: 2, n2: 30 },
     { id: 'S2', m1: 8,  s1: 2, n1: 30, m2: 7, s2: 2, n2: 30 },
     { id: 'S3', m1: 9,  s1: 2, n1: 30, m2: 6, s2: 2, n2: 30 }], 'cont', 'MD');
const mlPool = Engine.pool(mlEff, 'random', null, null, null);

console.log(JSON.stringify({
    matInv00: r(Ainv[0][0]),
    matInv11: r(Ainv[1][1]),
    matIdent00: r(ident[0][0]),
    mdFixedES: r(mdFixed.es),
    mdFixedSE: r(mdFixed.se),
    orPooledES: r(orPool.es),
    orDisplay: r(orPool.displayVal),
    mlI2: r(mlPool.I2),
    mlTau2b: r(mlPool.tau2_b),
    mlTau2w: r(mlPool.tau2_w),
    mlSeRobust: r(mlPool.se_r),
    mlPVal: r(mlPool.pVal)
}));
