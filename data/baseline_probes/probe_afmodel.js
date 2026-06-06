const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
const r = (x, n) => { const p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

// DL random-effects pooling, heterogeneous case from tests.js (ln(0.7)/SE0.1, ln(0.9)/SE0.2).
// Expected (hand-computed in tests.js): tau2 0.00657936, I2 20.8347, mu -0.2907040, se 0.110580.
const het = api.runDLMetaAnalysis(
  [
    { logOR: Math.log(0.7), SE: 0.1 },
    { logOR: Math.log(0.9), SE: 0.2 }
  ],
  'logOR', 'SE'
);

// DL pooling on metadat dat.bcg (yi/vi). vi fed as SE so SE^2 == vi.
// A correct DL pool gives est -0.714117, tau2 0.308758, I2 92.117 (Q recomputed with FE weights).
const bcgYi = [-0.889311,-1.585389,-1.348073,-1.441551,-0.217547,-0.786116,-1.620898,0.011952,-0.469418,-1.371345,-0.339359,0.445913,-0.017314];
const bcgVi = [0.325585,0.194581,0.415368,0.02001,0.05121,0.006906,0.223017,0.003962,0.056434,0.073025,0.012412,0.532506,0.071405];
const bcgData = bcgYi.map((y, i) => ({ yi: y, se: Math.sqrt(bcgVi[i]) }));
const bcg = api.runDLMetaAnalysis(bcgData, 'yi', 'se');

// Frequentist NMA, single trial A vs R, logOR -0.4 SE 0.1. A mean -0.4, R mean +0.4.
const fnma = api.runFrequentistNMA(
  [{ treatment: 'A', comparator: 'R', logOR_stroke: -0.4, SE_stroke: 0.1 }],
  ['R', 'A']
);
const drugA = fnma.posteriors.find(p => p.drug === 'A');

// Subgroup: FXa drug normal age/renal (all-ASCII inputs), adjEffect -0.2*1.05 = -0.21.
const sg = api.runSubgroupAnalysis(null, ['Apixaban'], '<65', '>60');

// League table: means -0.2 and 0.1, B-vs-A OR = exp(0.3) = 1.349859.
const lt = api.generateLeagueTable({ posteriors: [{ mean: -0.2 }, { mean: 0.1 }] }, ['A', 'B']);

// Heterogeneity risk heuristic, all four rules fire -> 70.
const hetRisk = api.calculateHeterogeneityRisk([
  { n_total: 1000, followup_years: 1, year: 2005 },
  { n_total: 2000, followup_years: 1, year: 2011 },
  { n_total: 3000, followup_years: 1, year: 2017 }
]);

// Dose-response OLS, slope -0.01, intercept 0.2.
const dr = api.runDoseResponseAnalysis([
  { treatment: 'Edoxaban 30mg', logOR_stroke: -0.1, SE_stroke: 0.1 },
  { treatment: 'Edoxaban 60mg', logOR_stroke: -0.4, SE_stroke: 0.1 }
], []);

// Net clinical benefit, posterior mean ln(0.5), strokeRisk 0.04 bleedRisk 0.02 -> ncb 0.0325.
const ncb = api.calculateNCB({ posteriors: [{ drug: 'X', mean: Math.log(0.5) }] }, 0.04, 0.02, 0);

console.log(JSON.stringify({
  het_mu: r(het.mu),
  het_tau2: r(het.tau2),
  het_I2: r(het.I2, 4),
  het_se: r(het.se),
  bcg_mu: r(bcg.mu),
  bcg_tau2: r(bcg.tau2),
  bcg_I2: r(bcg.I2, 4),
  fnma_A_mean: r(drugA.mean),
  subgrp_fxa_effect: r(sg[0].effect),
  league_BvA_or: r(lt[0][1].or),
  hetrisk_I2: r(hetRisk.predictedI2),
  dose_slope: r(dr.slope),
  ncb: r(ncb[0].ncb)
}));
