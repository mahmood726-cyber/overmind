# OVERMIND Daily Intelligence Report

**Day 1** | Generated: 2026-04-11T06:23:19+00:00

## Portfolio
- 612 projects | 322 testable | 218 advanced math
- Risk: {'high': 98, 'medium': 324, 'medium_high': 190}

## Verification Coverage
- **84/322 tested (26.1%)**
- High-risk unverified: 125
- Top unverified:
  - advanced-nma-pooling (risk=high, math=20)
  - DTA70 (risk=high, math=17)
  - Pairwise70 (risk=high, math=15)
  - Pairwise70 (risk=high, math=15)
  - rmstnma (risk=high, math=15)

## Regressions
- Active: 83
  - advanced-nma-pooling-6e3c8bdb: Nightly: advanced-nma-pooling REJECT
  - cardiooracle-6cb36757: Pass rate degraded: 16% -> 0%
  - cardiooracle-6cb36757: Nightly: CardioOracle FAIL
  - idea12-59249342: Nightly: idea12 REJECT
  - ipd-meta-pro-link-40520491: Pass rate degraded: 16% -> 0%
  - ipd-meta-pro-link-40520491: Nightly: ipd-meta-pro-link FAIL
  - prognostic-meta-5028c26a: Pass rate degraded: 16% -> 0%
  - prognostic-meta-5028c26a: Nightly: prognostic-meta FAIL
  - dataextractor-9c5488b5: Nightly: Dataextractor FAIL
  - evidence-inference-4c874004: Nightly: evidence-inference FAIL

## Runner Performance
- codex: q=0.800 (W:3 L:0)
- gemini: q=0.667 (W:1 L:0)
- test_runner: q=0.665 (W:114 L:57)
- claude: q=0.387 (W:168 L:267)

## Memory
- 198 memories (avg relevance: 0.48)
- Types: {'audit_snapshot': 84, 'project_learning': 1, 'heuristic': 30, 'regression': 83}
- Heuristics: 30

## Today's Targets
- FIX 83 active regression(s) first
- Verify 5 projects from priority queue (coverage: 26%)
- Next project: DTA70 (priority=25)

## Priority Queue (next to verify)
1. **DTA70** (priority=25, risk=high)
2. **Pairwise70** (priority=22, risk=high)
3. **advanced-nma-pooling** (priority=22, risk=high)
4. **Pairwise70** (priority=22, risk=high)
5. **rmstnma** (priority=22, risk=high)
6. **ctgov-search-strategies** (priority=22, risk=high)
7. **metasprint-dta** (priority=21, risk=high)
8. **Denominator_Calibrated_Living_NMA** (priority=20, risk=high)
9. **Cbamm** (priority=20, risk=high)
10. **meta-paradigm-shift** (priority=18, risk=high)

## Benchmark Tracking (40-day proof)
- Coverage: 26.1%
- Pass rate: 46.9%
- Total verifications: 610
- Regressions found: 58
- Memories: 198
- Heuristics learned: 30
- Q-router entries: 4

## Session Mining (Claude Code transcript analysis)
- Sessions analyzed: 30
- Total messages: 12735
- Failure signals: 3488 | Success signals: 949
- Top errors: {'ValueError': 81, 'SyntaxError': 51, 'TypeError': 48, 'ImportError': 27, 'AssertionError': 17, 'KeyError': 15, 'ModuleNotFoundError': 7}
- Most active: (52x), user(22x), index(19x), nightly_verify(4x), bbxaihll6(2x)
- Insights mined: 3
