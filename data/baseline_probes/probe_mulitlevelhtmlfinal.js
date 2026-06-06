const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
const Engine = api.Engine;
const Matrix = api.Matrix;
const r = (x, n) => { const p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

// Matrix anchor: inverse of A = [[4,3],[6,3]] (det = -6). From tests.js section 3.
var Ai = Matrix.inv([[4, 3], [6, 3]]);
var II = Matrix.dot(Ai, [[4, 3], [6, 3]]);

// Fixed-effect MD pooling, 2 effects in 1 cluster. From tests.js section 4.
var effMD = Engine.calcEffects(
    [{ id: 'A', m1: 10, s1: 2, n1: 10, m2: 5, s2: 2, n2: 10 },
     { id: 'A', m1: 12, s1: 3, n1: 20, m2: 6, s2: 3, n2: 20 }], 'cont', 'MD');
var poolMD = Engine.pool(effMD, 'fixed', null, null, null);

// Random-effects OR, two identical effects in two clusters. From tests.js section 5.
var effOR = Engine.calcEffects(
    [{ id: '1', e1: 10, n1: 100, e2: 20, n2: 100 },
     { id: '2', e1: 10, n1: 100, e2: 20, n2: 100 }], 'binary', 'OR');
var poolOR = Engine.pool(effOR, 'random', null, null, null);

// True multilevel structure: 3 studies / 4 effects, random. From tests.js section 6.
var effML = Engine.calcEffects(
    [{ id: 'S1', m1: 10, s1: 2, n1: 30, m2: 5, s2: 2, n2: 30 },
     { id: 'S1', m1: 11, s1: 2, n1: 30, m2: 5, s2: 2, n2: 30 },
     { id: 'S2', m1: 8,  s1: 2, n1: 30, m2: 7, s2: 2, n2: 30 },
     { id: 'S3', m1: 9,  s1: 2, n1: 30, m2: 6, s2: 2, n2: 30 }], 'cont', 'MD');
var poolML = Engine.pool(effML, 'random', null, null, null);

// Multilevel Egger small-study test, k=4 asymmetric OR. From tests.js section 12.
var effEgg = Engine.calcEffects(
    [{ id: '1', e1: 5,  n1: 100, e2: 20, n2: 100 },
     { id: '2', e1: 10, n1: 120, e2: 22, n2: 120 },
     { id: '3', e1: 30, n1: 200, e2: 35, n2: 200 },
     { id: '4', e1: 40, n1: 300, e2: 44, n2: 300 }], 'binary', 'OR');
var egg = Engine.multilevelEgger(effEgg);

console.log(JSON.stringify({
    mat_inv00: r(Ai[0][0]),
    mat_inv11: r(Ai[1][1]),
    mat_ident_trace: r(II[0][0] + II[1][1]),
    md_es: r(poolMD.es),
    md_se: r(poolMD.se),
    md_lo: r(poolMD.lo),
    md_hi: r(poolMD.hi),
    or_es: r(poolOR.es),
    or_disp: r(poolOR.displayVal),
    ml_i2: r(poolML.I2),
    ml_se_r: r(poolML.se_r),
    egg_intercept: r(egg.intercept, 5)
}));
