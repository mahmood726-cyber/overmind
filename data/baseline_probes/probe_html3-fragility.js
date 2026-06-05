const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
const r = (x) => Math.round(x * 1e6) / 1e6;
const main = api.fragility(20, 80, 6, 94, { alpha: 0.05, test: 'fisher' });
const strong = api.fragility(40, 60, 5, 95, { alpha: 0.05, test: 'fisher' });
const border = api.fragility(20, 80, 9, 91, { alpha: 0.05, test: 'fisher' });
console.log(JSON.stringify({
  main_FI: main.FI,
  main_significant: main.significant ? 1 : 0,
  main_p0: r(main.p0),
  main_FQ: r(main.FQ),
  strong_FI: strong.FI,
  border_FI: border.FI,
  fisher_p_20_80_6_94: r(api.fisherTwoSided(20, 80, 6, 94))
}));