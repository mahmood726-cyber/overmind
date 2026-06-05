const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
const r = (x, n) => { const p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };
const yi = [-0.889311,-1.585389,-1.348073,-1.441551,-0.217547,-0.786116,-1.620898,0.011952,-0.469418,-1.371345,-0.339359,0.445913,-0.017314];
const vi = [0.325585,0.194581,0.415368,0.02001,0.05121,0.006906,0.223017,0.003962,0.056434,0.073025,0.012412,0.532506,0.071405];
const reml = api.metaAnalyze(yi, vi, { method: 'REML' });
const dl = api.metaAnalyze(yi, vi, { method: 'DL' });
const pm = api.metaAnalyze(yi, vi, { method: 'PM' });
console.log(JSON.stringify({
  bcg_k: reml.k,
  reml_mu: r(reml.mu), reml_tau2: r(reml.tau2), reml_seMu: r(reml.seMu),
  dl_mu: r(dl.mu), dl_tau2: r(dl.tau2),
  pm_tau2: r(pm.tau2),
  Q: r(reml.Q, 4), I2: r(reml.I2, 4)
}));