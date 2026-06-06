const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
const r = (x, n) => { const p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

const allActive = {
    activeIds: ['PLA', 'SGLT2', 'ARNI', 'MRA', 'ARB', 'DIG'],
    endpoint: 'composite', view: 'topology',
    includeBadTopcat: false, interactionPenalty: 0.8
};
const topcatOn = {
    activeIds: ['PLA', 'SGLT2', 'ARNI', 'MRA', 'ARB', 'DIG'],
    endpoint: 'composite', view: 'topology',
    includeBadTopcat: true, interactionPenalty: 0.8
};
const arniIsolated = {
    activeIds: ['PLA', 'SGLT2', 'ARNI'],
    endpoint: 'composite', view: 'topology',
    includeBadTopcat: false, interactionPenalty: 0.8
};

const sg = api.TRIALS.find(t => t.name === 'Pooled SGLT2');
const topcat = api.TRIALS.find(t => t.name === 'TOPCAT');
const nb = api.calculateNetBenefit(allActive);

console.log(JSON.stringify({
    n_treatments: api.TREATMENTS.length,
    n_trials: api.TRIALS.length,
    w_sglt2: r(api.getEdgeWeight(sg, allActive)),
    w_topcat_off: r(api.getEdgeWeight(topcat, allActive)),
    w_topcat_on: r(api.getEdgeWeight(topcat, topcatOn)),
    net_total_hr: r(nb.totalHR),
    net_real_hr: r(nb.realHR),
    net_safety: r(nb.safetyScore),
    bridged_arni_composite: r(api.bridgedArniHR('composite')),
    bridged_arni_mortality: r(api.bridgedArniHR('mortality')),
    total_events_off: r(api.totalEvents(allActive)),
    total_events_on: r(api.totalEvents(topcatOn)),
    era_span: r(api.eraSpan(allActive)),
    connected_full: api.isConnected(allActive) ? 1 : 0,
    connected_arni_isolated: api.isConnected(arniIsolated) ? 1 : 0
}));
