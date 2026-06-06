// Deterministic baseline probe for WaterNajia scoring engine.
// For Overmind NumericalWitness. Prints ONE line of JSON of stable numeric scalars.
// Inputs are the EXACT fixed cases tests.js validates (seed 12345, deterministic
// XorShift128Plus Monte Carlo). Golden P values are pinned in tests.js:
//   G1 piped_chlorinated         P == 0.047715
//   G2 surface_water             P == 0.579607
//   G3 protected_well flood 12h  P == 0.662842
//   G4 protected_well flood 72h  P == 0.313101
// No Date/Math.random/file reads; engine seeds its own PRNG with the literal seed.
var path = require('path');
var api = require(path.resolve(process.cwd(), 'engine.js'));
var r = function (x, n) { var p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

var MODEL = api.MODEL;
var SEED = 12345;

var BASE = {
    is_vulnerable: false, heavy_rain: false, flooding: false,
    hours_since_rain_or_flood: null, turbidity_visible: false,
    smell_or_taste_change: false, storage_uncovered_over_24h: false,
    storage_uncovered_over_48h: false, animals_access_or_open_container: false,
    latrine_under_10m: false, latrine_10_to_30m: false,
    dirty_fetch_container: false, diarrhoea_signal_mild: false,
    diarrhoea_signal_strong: false
};

function withBase(extra) {
    var o = {};
    for (var k in BASE) { o[k] = BASE[k]; }
    for (var j in extra) { o[j] = extra[j]; }
    return o;
}

// Golden cases from tests.js
var g1 = api.computeRisk(withBase({ source_type: 'piped_chlorinated' }), MODEL, SEED);
var g2 = api.computeRisk(withBase({ source_type: 'surface_water' }), MODEL, SEED);
var g3 = api.computeRisk(withBase({ source_type: 'protected_well', flooding: true, hours_since_rain_or_flood: 12 }), MODEL, SEED);
var g4 = api.computeRisk(withBase({ source_type: 'protected_well', flooding: true, hours_since_rain_or_flood: 72 }), MODEL, SEED);

// Deterministic building blocks (exact, hand-checkable in tests.js)
var sig0 = api.sigmoid(0);
var logit05 = api.logit(0.05);
var decay12 = api.decay(12, 36, 120);

console.log(JSON.stringify({
    g1_piped_P: r(g1.P),
    g2_surface_P: r(g2.P),
    g3_flood12_P: r(g3.P),
    g4_flood72_P: r(g4.P),
    g3_min: r(g3.min),
    g3_max: r(g3.max),
    g2_confidence: r(g2.confidence),
    g3_missing: r(g3.missingCount),
    g3_is_high: g3.category === 'high' ? 1 : 0,
    sigmoid0: r(sig0),
    logit_005: r(logit05),
    decay12: r(decay12)
}));
