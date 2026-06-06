const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
const r = (x, n) => { const p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

const Engine = api.Engine;

// Triangle network (tau2 = 0), hand-derived in tests.js.
// Contrasts: A-B=0.5, B-C=0.3, A-C=0.8, all se=0.1.
var triCs = [
    { study: 'S1', t1: 'A', t2: 'B', es: 0.5, se: 0.1 },
    { study: 'S2', t1: 'B', t2: 'C', es: 0.3, se: 0.1 },
    { study: 'S3', t1: 'A', t2: 'C', es: 0.8, se: 0.1 }
];
var triTs = ['A', 'B', 'C'];
var tri = Engine.estimate(triCs, triTs, 0);
var thA = tri.theta[0];
var thB = tri.theta[1];
var thC = tri.theta[2];
var varAB = tri.V[0][0] + tri.V[1][1] - 2 * tri.V[0][1];
var ps = Engine.pScores(tri.theta, tri.V, false);
var psA = ps[0];
var psSum = ps.reduce(function (a, b) { return a + b; }, 0);

// Two 2-arm A-B studies (tau2 = 0): IV pooled = 0.56, var = 0.008, Q = 0.80.
var twoCs = [
    { study: 'S1', t1: 'A', t2: 'B', es: 0.4, se: 0.2 },
    { study: 'S2', t1: 'A', t2: 'B', es: 0.6, se: 0.1 }
];
var twoTs = ['A', 'B'];
var two = Engine.estimate(twoCs, twoTs, 0);
var pooledAB = two.theta[0] - two.theta[1];
var varPooled = two.V[0][0] + two.V[1][1] - 2 * two.V[0][1];
var Q = two.Q;

// Statistical primitives.
var pnorm975 = Engine.pnorm(1.959964);
var qnorm975 = Engine.qnorm(0.975);
var i2 = Engine.I2(100, 10);

// Matrix inverse closed form: A = [[4,7],[2,6]] -> Ai[0][0] = 0.6.
var Ai = Engine.inv([[4, 7], [2, 6]]);
var inv00 = Ai[0][0];

console.log(JSON.stringify({
    thA: r(thA),
    thB: r(thB),
    thC: r(thC),
    varAB: r(varAB),
    psA: r(psA),
    psSum: r(psSum),
    pooledAB: r(pooledAB),
    varPooled: r(varPooled),
    Q: r(Q),
    pnorm975: r(pnorm975),
    qnorm975: r(qnorm975),
    i2: r(i2),
    inv00: r(inv00)
}));
