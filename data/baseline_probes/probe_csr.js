const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
const r = (x, n) => { const p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

// Fixed inputs taken VERBATIM from tests.js hand-worked examples.
// computeStructure: the s3 study set (rho 0.1/0.2/0.3, authors A,B / B,C / A).
const st = api.computeStructure([
    { rho: 0.1, authors: ['A', 'B'] },
    { rho: 0.2, authors: ['B', 'C'] },
    { rho: 0.3, authors: ['A'] }
]);

// runKalman: the two-study series effect 1.0/2.0, se 0.5, years 2020/2021.
const kf = api.runKalman([
    { effect: 1.0, se: 0.5, year: 2020 },
    { effect: 2.0, se: 0.5, year: 2021 }
]);

console.log(JSON.stringify({
    lambda1: r(st.lambda1),
    lambda2: r(st.lambda2),
    gap: r(st.gap),
    Neff: r(st.Neff),
    Cab: r(st.Cab),
    kf_mu0: r(kf.history[0].mu),
    kf_P0: r(kf.history[0].P),
    kf_mu1: r(kf.history[1].mu),
    kf_P1: r(kf.history[1].P),
    finalMu: r(kf.finalMu),
    DSI: r(kf.DSI)
}));
