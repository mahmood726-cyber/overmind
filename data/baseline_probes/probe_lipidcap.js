const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
const r = (x, n) => { const p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

// Deterministic fixed inputs taken from tests.js (rng constant 0.5, fixed slopeSD).
// All paths are exact and hand-checkable; no stochastic tolerance needed.

// Potency / kinetics (CTT log-linear core).
var comboPot = api.addedPotency('combo');                 // 1-(1-0.60)(1-0.18) = 0.672
var kin = api.ldlKinetics(100, 'pcsk9');                  // final 40, dmg 60, dmmol 1.5516
var prr = api.patientRR(Math.log(0.78), 1.5516);          // exp(ln0.78*1.5516) = 0.6801019
var bm = api.boxMuller(0.5, 0.5);                          // -1.1774100

// Deterministic full projection: pcsk9, slopeSD=0, rng=0.5 -> every iter identical.
var proj = api.runProjection({
    baselineLDL: 100, baselineRisk: 20, strategy: 'pcsk9',
    hetPenalty: 0, iterations: 1000, slopeSD: 0, rng: function () { return 0.5; }
});

// Heterogeneity-scaled projection: hetPenalty=100 (hf=1.5), slopeSD=0.03, rng=0.5.
var projHet = api.runProjection({
    baselineLDL: 100, baselineRisk: 20, strategy: 'pcsk9',
    hetPenalty: 100, iterations: 500, slopeSD: 0.03, rng: function () { return 0.5; }
});

// Ezetimibe projection: slopeSD=0, rng=0.5.
var projEze = api.runProjection({
    baselineLDL: 100, baselineRisk: 20, strategy: 'eze',
    iterations: 100, slopeSD: 0, rng: function () { return 0.5; }
});

var nnt = api.nntFromARR(proj.meanARR);                   // round(1/0.03198981) = 31

console.log(JSON.stringify({
    combo_potency: r(comboPot, 6),
    delta_ldl_mmol: r(kin.deltaLDL_mmol, 6),
    patient_rr: r(prr, 6),
    box_muller: r(bm, 6),
    proj_mean_arr: r(proj.meanARR, 8),
    proj_mean_rrr: r(proj.meanRRR, 6),
    proj_n_prevented: r(proj.n_prevented, 0),
    proj_n_inevitable: r(proj.n_event_inevitable, 0),
    proj_n_healthy: r(proj.n_healthy, 0),
    proj_het_mean_rrr: r(projHet.meanRRR, 6),
    eze_mean_rrr: r(projEze.meanRRR, 6),
    nnt: r(nnt, 0)
}));
