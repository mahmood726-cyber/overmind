const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
var r = function (x, n) { var p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

var A = api.calculateStats({ n: 1000, eventsTx: 100, eventsCtl: 100 });
var B = api.calculateStats({ n: 200, eventsTx: 10, eventsCtl: 20 });
var D = api.calculateStats({ n: 100, eventsTx: 0, eventsCtl: 5 });

var bayes = api.runFragilitySimulation([], 'Bayesian', 0);
var freq = api.runFragilitySimulation([], 'Frequentist', 0);

console.log(JSON.stringify({
  A_logHR: r(A.logHR),
  A_varLogHR: r(A.varLogHR),
  B_logHR: r(B.logHR),
  B_varLogHR: r(B.varLogHR),
  D_logHR: r(D.logHR),
  D_varLogHR: r(D.varLogHR),
  erf1: r(api.erf(1)),
  bayes_i0_probHarm: r(bayes[0].probHarm),
  bayes_i60_probHarm: r(bayes[60].probHarm),
  freq_i16_snapped: freq[16].probHarm === 1.0 ? 1 : 0
}));
