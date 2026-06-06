// Deterministic baseline probe for the Oman Evidence OS engine.
// Run with cwd = project dir. Prints exactly one JSON line of numeric scalars.
// All randomness is via the seeded mulberry32 PRNG with a fixed seed.
var path = require('path');
var api = require(path.resolve(process.cwd(), 'engine.js'));
var NMA = api.NMA;
var runMarkovTrace = api.runMarkovTrace;
var mulberry32 = api.mulberry32;

var r = function(x, n) { var p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

// NMA: exact tests.js fixed input (single 2-treatment study, control t4=10/100, drug t1=20/100).
// Expected: t1 logOR = ln(2.25) = 0.8109302162, OR = 2.25, se = sqrt(0.1736111).
var nma = NMA.computeNMA({
    effects: { t1: { name: 'Drug' }, t4: { name: 'Control' } },
    trials: [{ id: 'S1', drug: 't1', ctrl: 't4', ev_tx: 20, n_tx: 100, ev_ctrl: 10, n_ctrl: 100 }]
});
var pT1 = 0, pT4 = 0;
for (var i = 0; i < nma.rankings.length; i++) {
    if (nma.rankings[i].key === 't1') pT1 = nma.rankings[i].pScore;
    if (nma.rankings[i].key === 't4') pT4 = nma.rankings[i].pScore;
}

// calcLogOR: tests.js hand case (10/100 vs 20/100) -> ln(2.25), var = sum reciprocals.
var lor = NMA.calcLogOR(10, 100, 20, 100);

// normalCDF reference point (tests.js): Phi(1.96) ~ 0.975.
var phi = NMA.normalCDF(1.96);

// runMarkovTrace: pure deterministic. tests.js undiscounted case -> cost 1000, QALY 10.
var mk = runMarkovTrace({ costAnnual: 100, costEvent: 0, utilState: 1, probEvent: 0, probDeath: 0, discount: 0 });
// Discounted + mortality variant for a non-trivial deterministic value.
var mkD = runMarkovTrace({ costAnnual: 100, costEvent: 50, utilState: 0.8, probEvent: 0.1, probDeath: 0.05, discount: 0.035 });

// mulberry32: fixed-seed deterministic draws (tests.js uses seed 12345).
var rng = mulberry32(12345);
var d1 = rng();
var d2 = rng();
var d3 = rng();

console.log(JSON.stringify({
    nma_t1_logOR: r(nma.effects.t1.logOR),
    nma_t1_or: r(nma.effects.t1.or),
    nma_t1_se: r(nma.effects.t1.se),
    nma_pscore_t1: r(pT1),
    nma_pscore_sum: r(pT1 + pT4),
    nma_ntreat: nma.treatments.length,
    calc_logor: r(lor.logOR),
    calc_var: r(lor.variance),
    normcdf_196: r(phi),
    markov_cost: r(mk.c),
    markov_qaly: r(mk.e),
    markov_disc_cost: r(mkD.c),
    markov_disc_qaly: r(mkD.e),
    rng_d1: r(d1),
    rng_d2: r(d2),
    rng_d3: r(d3)
}));
