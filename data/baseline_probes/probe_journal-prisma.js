const path = require('path');
const api = require(path.resolve(process.cwd(), 'engine.js'));

var counts = {
  recordsDb: 800, recordsOther: 200, duplicatesRemoved: 300,
  recordsScreened: 700, recordsExcluded: 600,
  reportsSought: 100, reportsNotRetrieved: 10, reportsAssessed: 90,
  excludedReasons: [
    { reason: 'Wrong population', n: 20 },
    { reason: 'Wrong outcome', n: 15 },
    { reason: 'No control arm', n: 10 }
  ],
  studiesIncluded: 45, reportsIncluded: 50
};

var rc = api.reconcile(counts);
var bs = api.buildStages(counts);
var inclStage = bs.stages[bs.stages.length - 1];

console.log(JSON.stringify({
  recordsDb: rc.flow.recordsDb,
  recordsOther: rc.flow.recordsOther,
  duplicatesRemoved: rc.flow.duplicatesRemoved,
  derivedScreened: rc.derived.recordsScreened,
  derivedAssessed: rc.derived.reportsAssessed,
  derivedIncluded: rc.derived.studiesIncluded,
  sumExcluded: api.sumExcluded(counts.excludedReasons),
  sumExcludedReasons: rc.sumExcludedReasons,
  warningsCount: rc.warnings.length,
  stagesCount: bs.stages.length,
  inclStageN: inclStage.n,
  inclExitsCount: inclStage.exits.length,
  checklistLength: api.CHECKLIST.length
}));
