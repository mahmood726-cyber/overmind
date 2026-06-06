var path = require('path');
var api = require(path.resolve(process.cwd(), 'engine.js'));
var r = function (x, n) { var p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

// metadat dat.bcg on the log scale (yi/vi). metafor DL RE cross-check:
// est=-0.714117, tau2=0.308758, Q=152.2268, I2=92.117.
var yi = [-0.889311, -1.585389, -1.348073, -1.441551, -0.217547, -0.786116,
          -1.620898, 0.011952, -0.469418, -1.371345, -0.339359, 0.445913, -0.017314];
var vi = [0.325585, 0.194581, 0.415368, 0.02001, 0.05121, 0.006906, 0.223017,
          0.003962, 0.056434, 0.073025, 0.012412, 0.532506, 0.071405];
var bcg = yi.map(function (y, i) { return { study: 's' + i, effect: y, se: Math.sqrt(vi[i]) }; });

var dl = api.metaDL(bcg);
var reml = api.metaREML(bcg);
var hk = api.applyHKSJ(dl, bcg);
var pi = api.calcPredictionInterval(dl, bcg);
var t2 = api.tau2CI(bcg, dl.tau2);
var eg = api.eggersTest(bcg);

// tests.js exact two-study DL closed form: thetaRE=-0.2907036, tau2=0.00657947.
var s2 = [{ study: 'A', effect: Math.log(0.70), se: 0.10 },
          { study: 'B', effect: Math.log(0.90), se: 0.20 }];
var dl2 = api.metaDL(s2);

console.log(JSON.stringify({
    bcg_dl_effect: r(dl.effect),
    bcg_dl_se: r(dl.se),
    bcg_dl_tau2: r(dl.tau2),
    bcg_dl_Q: r(dl.Q, 4),
    bcg_dl_I2: r(dl.I2, 4),
    bcg_reml_tau2: r(reml.tau2),
    bcg_hksj_se: r(hk.se),
    bcg_pi_lower: r(pi.piLower),
    bcg_tau2ci_upper: r(t2.upper, 4),
    bcg_egger_p: r(eg.pValue),
    s2_dl_effect: r(dl2.effect),
    s2_dl_tau2: r(dl2.tau2)
}));
