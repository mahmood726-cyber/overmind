// Deterministic numerical baseline probe for the NutriLogic / UPF engine.
// For Overmind NumericalWitness. Prints exactly ONE line of JSON of stable
// numeric scalars. Inputs are the exact fixtures tests.js hand-computes.
// ASCII only; no backslashes; no template literals; no Date/random/file reads.

var path = require('path');
var api = require(path.resolve(process.cwd(), 'engine.js'));
var r = function (x, n) { var p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

// Fixed-effect, 2 heterogeneous cohorts (tests.js lines 63-73).
// Hand-computed expectations: HR=1.11363, lo=1.04134, hi=1.19094, p=0.001673.
var fe = api.runFixedEffect(api.adjustCohorts([
    { id: 'c1', hr: 1.20, lo: 1.10, hi: 1.31 },
    { id: 'c2', hr: 1.00, lo: 0.90, hi: 1.11 }
], {}));

// HKSJ, 2 identical cohorts -> Q=0, floor binds (tests.js lines 83-92).
// Hand-computed: HR=1.10, lo=0.80550, hi=1.50218, I2=0, critVal=12.706.
var idn = api.runHKSJ(api.adjustCohorts([
    { id: 'x', hr: 1.10, lo: 1.03, hi: 1.18 },
    { id: 'x', hr: 1.10, lo: 1.03, hi: 1.18 }
], {}));

// HKSJ on the heterogeneous pair via top-level dispatch (random model).
var re = api.runMetaAnalysis([
    { id: 'c1', hr: 1.20, lo: 1.10, hi: 1.31 },
    { id: 'c2', hr: 1.00, lo: 0.90, hi: 1.11 }
], { modelType: 'random' });

console.log(JSON.stringify({
    fe_hr: r(fe.hr),
    fe_lo: r(fe.lo),
    fe_hi: r(fe.hi),
    fe_p: r(fe.p),
    fe_I2: r(fe.I2),
    idn_hr: r(idn.hr),
    idn_lo: r(idn.lo),
    idn_hi: r(idn.hi),
    idn_crit: r(idn.critVal),
    re_hr: r(re.hr),
    re_I2: r(re.I2),
    re_crit: r(re.critVal)
}));
