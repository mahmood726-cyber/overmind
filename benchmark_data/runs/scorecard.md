# Benchmark scorecard

Slice: F:\overmind\benchmark_data  
Held-out tasks: 35  
Generated: (stamp on write)

| arm | status | caught-defect | false-alarm | parity | agreement | accepted | cost/accepted | blended |
|---|---|---|---|---|---|---|---|---|
| objective-ref (witness-only floor) | RUN | 0.6538 | 0.0000 | 1.0000 | 0.5000 | 18 | 0.0000 | 1.1538 |
| C-shadow (stub reviewers) | SHADOW | 1.0000 | 0.0000 | 1.0000 | 1.0000 | 9 | 0.0000 | 1.5000 |
| A | STAGED (needs a live frontier model) | n/a | n/a | n/a | n/a | - | n/a | n/a |
| B | STAGED (needs a live frontier model x3) | n/a | n/a | n/a | n/a | - | n/a | n/a |
| C | STAGED (needs >=2 distinct live families; have []) | n/a | n/a | n/a | n/a | - | n/a | n/a |

## Win condition
_Pending: needs Arms A, B, C all run (model capacity)._

## Notes
- Held-out slice: 35 tasks from 64 total (defects=26, clean=9).
- Held-out split is a deterministic sha256 bucket; answer keys read only by the scorer.
- Weights pinned (BENCHMARK.md/scoring.py); scoring can report NOT_PROVEN.
- Objective reference = Arm C floor with NO reviewers: catches witness-detectable defects (impossible_cell, reproduction) but structurally misses reviewer-only 'direction' defects — that gap is what the cross-vendor panel must close.
- Live vendors this run: NONE (all capped/unauthed).
