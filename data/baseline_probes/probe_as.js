const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
const r = (x, n) => { const p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };
const yi = [-0.889311,-1.585389,-1.348073,-1.441551,-0.217547,-0.786116,-1.620898,0.011952,-0.469418,-1.371345,-0.339359,0.445913,-0.017314];
const vi = [0.325585,0.194581,0.415368,0.02001,0.05121,0.006906,0.223017,0.003962,0.056434,0.073025,0.012412,0.532506,0.071405];
const se = vi.map(Math.sqrt);
const res = api.calculateMetaAnalysis(yi.map((y, i) => ({ hr: Math.exp(y), ci_lower: Math.exp(y - 1.96 * se[i]), ci_upper: Math.exp(y + 1.96 * se[i]), n: 100 })));
console.log(JSON.stringify({
  pooledLogHR: r(res.pooledLogHR), pooledHR: r(res.pooledHR), tau2: r(res.tau2),
  Q: r(res.Q, 4), df: res.df, I2: r(res.I2, 4)
}));