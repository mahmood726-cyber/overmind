# OVERMIND Daily Intelligence Report

**Day 1** | Generated: 2026-04-09T18:48:55+00:00

## Portfolio
- 592 projects | 305 testable | 205 advanced math
- Risk: {'high': 96, 'medium_high': 179, 'medium': 317}

## Verification Coverage
- **83/305 tested (27.2%)**
- High-risk unverified: 115
- Top unverified:
  - advanced-nma-pooling (risk=high, math=20)
  - DTA70 (risk=high, math=17)
  - Pairwise70 (risk=high, math=15)
  - rmstnma (risk=high, math=15)
  - Pairwise70 (risk=high, math=15)

## Regressions
- Active: 67
  - bayesianma-240f4a74: Verification failed
  - bayesianma-240f4a74: Pass rate degraded: 54% -> 0%
  - cardiooracle-6cb36757: Pass rate degraded: 16% -> 0%
  - cardiooracle-6cb36757: Nightly: CardioOracle FAIL
  - dataextractor-backup-20260114-110706-2be04ee7: Nightly: Dataextractor FAIL
  - idea12-59249342: Nightly: idea12 FAIL
  - metasprint-autopilot-0016fbe9: Nightly: metasprint-dta FAIL
  - superapp-39dd1793: Nightly: superapp FAIL
  - evidence-inference-4c874004: Nightly: EvidenceOracle REJECT
  - cbamm-0820ec88: Nightly: Cbamm FAIL

## Runner Performance
- codex: q=0.800 (W:3 L:0)
- gemini: q=0.667 (W:1 L:0)
- test_runner: q=0.664 (W:90 L:45)
- claude: q=0.386 (W:129 L:206)

## Memory
- 177 memories (avg relevance: 0.70)
- Types: {'audit_snapshot': 83, 'project_learning': 1, 'heuristic': 26, 'regression': 67}
- Heuristics: 26

## Today's Targets
- FIX 67 active regression(s) first
- Verify 5 projects from priority queue (coverage: 27%)
- Next project: DTA70 (priority=25)

## Priority Queue (next to verify)
1. **DTA70** (priority=25, risk=high)
2. **Pairwise70** (priority=22, risk=high)
3. **rmstnma** (priority=22, risk=high)
4. **Pairwise70** (priority=22, risk=high)
5. **advanced-nma-pooling** (priority=22, risk=high)
6. **ctgov-search-strategies** (priority=22, risk=high)
7. **metasprint-dta** (priority=21, risk=high)
8. **Denominator_Calibrated_Living_NMA** (priority=20, risk=high)
9. **Cbamm** (priority=20, risk=high)
10. **MLMResearch** (priority=18, risk=high)

## Benchmark Tracking (40-day proof)
- Coverage: 27.2%
- Pass rate: 47.0%
- Total verifications: 474
- Regressions found: 53
- Memories: 177
- Heuristics learned: 26
- Q-router entries: 4

## Session Mining (Claude Code transcript analysis)
- Sessions analyzed: 30
- Total messages: 8969
- Failure signals: 2564 | Success signals: 825
- Top errors: {'SyntaxError': 54, 'ValueError': 51, 'ImportError': 46, 'TypeError': 24, 'ModuleNotFoundError': 18, 'KeyError': 14, 'AssertionError': 10}
- Most active: (58x), user(31x), index(19x), nightly_verify(6x), code_generator(4x)
- Insights mined: 3
