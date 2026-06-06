const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
const Stats = api.Stats;
const MetaEngine = api.MetaEngine;
const r = function (x, n) { const p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

// Fixed-effect 2-study fixture (verbatim from tests.js hand-worked block).
function study(id, hr, lo, hi) {
    return { id: id, verdict: { status: 'PASS', docket: {
        'contrast.effect': { value: hr },
        'contrast.ciLo': { value: lo },
        'contrast.ciHi': { value: hi }
    } } };
}
const feData = MetaEngine.prepareData([
    study('S1', 0.74, 0.65, 0.85),
    study('S2', 0.82, 0.73, 0.92)
]).data;
const fe = MetaEngine.pool(feData, 'fixed', false);

// DerSimonian-Laird random-effects fixture: metafor dat.bcg (log risk ratio).
// Fed through the analysis_ready fast path as log_effect (yi) and vi.
const yi = [-0.889311, -1.585389, -1.348073, -1.441551, -0.217547, -0.786116, -1.620898, 0.011952, -0.469418, -1.371345, -0.339359, 0.445913, -0.017314];
const vi = [0.325585, 0.194581, 0.415368, 0.02001, 0.05121, 0.006906, 0.223017, 0.003962, 0.056434, 0.073025, 0.012412, 0.532506, 0.071405];
const bcgStudies = yi.map(function (y, i) {
    return { id: 'bcg' + i, verdict: { status: 'PASS' }, analysis_ready: { log_effect: y, vi: vi[i], effect: Math.exp(y) } };
});
const bcgData = MetaEngine.prepareData(bcgStudies).data;
const reDL = MetaEngine.pool(bcgData, 'random', false);

console.log(JSON.stringify({
    fe_effect: r(fe.effect),
    fe_Q: r(fe.Q),
    fe_I2: r(fe.I2),
    fe_p: r(fe.p),
    bcg_logEffect: r(Math.log(reDL.effect)),
    bcg_tau2: r(reDL.tau2),
    bcg_Q: r(reDL.Q, 4),
    bcg_I2: r(reDL.I2),
    bcg_df: r(reDL.df),
    tcrit_df10: r(Stats.tCritical(10)),
    ncdf_196: r(Stats.normalCdf(1.96)),
    nq_975: r(Stats.normalQuantile(0.975))
}));
