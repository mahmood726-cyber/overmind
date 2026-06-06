const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
const r = (x, n) => { const p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };
const yi = [-0.889311,-1.585389,-1.348073,-1.441551,-0.217547,-0.786116,-1.620898,0.011952,-0.469418,-1.371345,-0.339359,0.445913,-0.017314];
const vi = [0.325585,0.194581,0.415368,0.02001,0.05121,0.006906,0.223017,0.003962,0.056434,0.073025,0.012412,0.532506,0.071405];
const se = vi.map(Math.sqrt);
const res = api.runHKSJ(yi.map((y, i) => ({ logOR: y, se: se[i], id: 'S' + i })), 'logOR', 'se');
console.log(JSON.stringify({
  k: res.k, or: r(res.or), lo: r(res.lo), hi: r(res.hi), tau2: r(res.tau2), I2: r(res.I2, 4)
}));