# Benchmark scorecard

Slice: F:\overmind\benchmark_data  
Held-out tasks: 164  
Generated: (stamp on write)

| arm | status | caught-defect | false-alarm | parity | agreement | accepted | cost/accepted | blended |
|---|---|---|---|---|---|---|---|---|
| objective-ref (witness-only floor) | RUN | 0.3082 | 0.0000 | 1.0000 | 0.1513 | 119 | 0.0000 | 0.8082 |
| C-shadow (stub reviewers) | SHADOW | 1.0000 | 0.0000 | 1.0000 | 1.0000 | 18 | 0.0000 | 1.5000 |
| A | STAGED (needs a live frontier model) | n/a | n/a | n/a | n/a | - | n/a | n/a |
| B | STAGED (needs a live frontier model x3) | n/a | n/a | n/a | n/a | - | n/a | n/a |
| C | STAGED (needs >=2 distinct live families; have []) | n/a | n/a | n/a | n/a | - | n/a | n/a |

## Win condition
_Pending: needs Arms A, B, C all run (model capacity)._

## Notes
- Held-out slice: 164 tasks from 330 total (defects=146, clean=18).
- Held-out split is a deterministic sha256 bucket; answer keys read only by the scorer.
- Weights pinned (BENCHMARK.md/scoring.py); scoring can report NOT_PROVEN.
- Objective reference = Arm C floor with NO reviewers: catches witness-detectable defects (impossible_cell, reproduction, ci_invalid) but structurally misses the 101 reviewer-only defects in the held-out slice (6 classes) — that gap is what the cross-vendor panel must close.
- Live vendors this run: NONE (all capped/unauthed).
