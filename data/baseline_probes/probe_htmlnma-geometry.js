const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));
const r = (x, n) => { const p = Math.pow(10, n == null ? 6 : n); return Math.round(x * p) / p; };

// Fixed networks taken verbatim from tests.js fixtures.
var aggInput = 'A, B, 2\nA, B, 3\nB, C\nA, C';   // parallel-edge aggregation triangle
var starInput = 'H, A\nH, B\nH, C\nH, D';         // star network, hub degree 4
var discInput = 'A, B\nC, D';                      // two disconnected components

var parsed = api.parseInput(aggInput);
var g = api.buildGraph(parsed.studies);
var comps = api.connectedComponents(g.nodes, g.edges);
var checklist = api.transitivityChecklist();
var agg = api.inspect(aggInput);
var star = api.inspect(starInput);
var disc = api.inspect(discInput);

// aggregated A-B edge weight (2 + 3 = 5)
var abEdge = g.edges.filter(function (e) {
  return api.edgeKey(e.a, e.b) === api.edgeKey('A', 'B');
})[0];

var checklistTotal = checklist.length;
var checklistUnconfirmed = checklist.filter(function (c) { return c.confirmed === null; }).length;

console.log(JSON.stringify({
  aggNodes: r(g.nodes.length),
  aggEdges: r(g.edges.length),
  aggComponents: r(comps.length),
  aggConnected: agg.connected ? 1 : 0,
  aggFeasible: agg.nmaFeasible ? 1 : 0,
  aggTotalStudies: r(agg.totalStudies),
  aggAbEdgeN: r(abEdge ? abEdge.n : -1),
  aggDensity: r(agg.density),
  starHubDegree: r(star.mostConnected ? star.mostConnected.degree : -1),
  discComponents: r(disc.components),
  discFeasible: disc.nmaFeasible ? 1 : 0,
  checklistTotal: r(checklistTotal),
  checklistUnconfirmed: r(checklistUnconfirmed)
}));
