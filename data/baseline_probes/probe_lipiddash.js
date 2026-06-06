const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
var TRIALS = api.TRIALS, filterTrials = api.filterTrials, computePooled = api.computePooled, computeNNT = api.computeNNT;
var r = function (x, n) { var p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

// Full bundled dataset, default state: MACE, duration 5, all trials.
var full = computePooled(TRIALS, { includeLowRisk: true, metric: 'RRR', outcome: 'MACE', duration: 5.0 });
// De-diluted: exclude low-risk (drops all 6 primary-prevention trials).
var dedil = computePooled(TRIALS, { includeLowRisk: false, metric: 'RRR', outcome: 'MACE', duration: 5.0 });
// Mortality outcome path, full dataset.
var mort = computePooled(TRIALS, { includeLowRisk: true, metric: 'RRR', outcome: 'MORT', duration: 5.0 });

console.log(JSON.stringify({
    full_avgRRR: r(full.avgRRR),
    full_avgARR: r(full.avgARR),
    full_nnt: full.nnt,
    full_active: full.activeTrials.length,
    dedil_avgRRR: r(dedil.avgRRR),
    dedil_avgARR: r(dedil.avgARR),
    dedil_nnt: dedil.nnt,
    dedil_active: dedil.activeTrials.length,
    mort_avgRRR: r(mort.avgRRR),
    nnt_guard_pos: computeNNT(0.020),
    nnt_guard_zero: computeNNT(0) === '>1000' ? 1 : 0,
    n_trials: TRIALS.length,
    n_filter_excl: filterTrials(TRIALS, false).length
}));
