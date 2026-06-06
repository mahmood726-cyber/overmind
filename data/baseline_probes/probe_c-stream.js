// Deterministic baseline probe for C-Stream engine (Overmind NumericalWitness).
// Runs with cwd = project dir. Prints exactly ONE line of JSON of stable scalars.
// Uses ONLY deterministic paths: Meta.dersimonianLaird, Meta.leaveOneOut,
// Sensitivity, VOI, M.Phi/M.qnorm. Avoids all Math.random paths
// (M.randn, M.sampleWithReplacement, Bootstrap.run).
var path = require('path');
var api = require(path.resolve(process.cwd(), 'engine.js'));
var M = api.M, Meta = api.Meta, Sensitivity = api.Sensitivity, VOI = api.VOI;
var r = function (x, n) { var p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

// metafor dat.bcg log-effect + variance (DL RE cross-check:
// est=-0.714117, tau2=0.308758, Q=152.2268).
var yi = [-0.889311, -1.585389, -1.348073, -1.441551, -0.217547, -0.786116, -1.620898, 0.011952, -0.469418, -1.371345, -0.339359, 0.445913, -0.017314];
var vi = [0.325585, 0.194581, 0.415368, 0.02001, 0.05121, 0.006906, 0.223017, 0.003962, 0.056434, 0.073025, 0.012412, 0.532506, 0.071405];
var bcg = Meta.dersimonianLaird(yi, vi);

// tests.js hand-worked heterogeneous two-study case.
var het = Meta.dersimonianLaird([-0.40, 0.20], [0.01, 0.04]);
var loo = Meta.leaveOneOut([-0.40, 0.20], [0.01, 0.04]);

console.log(JSON.stringify({
    bcg_pooled: r(bcg.pooled),
    bcg_pooledSE: r(bcg.pooledSE),
    bcg_tau2: r(bcg.tau2),
    bcg_Q: r(bcg.Q, 4),
    bcg_I2: r(bcg.I2, 4),
    het_pooled: r(het.pooled),
    het_tau2: r(het.tau2),
    het_Q: r(het.Q),
    het_I2: r(het.I2, 4),
    loo0_influence: r(loo[0].influence),
    evalue_rr2: r(Sensitivity.eValueRR(2)),
    evpi_std: r(VOI.evpiNormal(0, 1, 0)),
    qnorm975: r(M.qnorm(0.975)),
    phi196: r(M.Phi(1.96))
}));
