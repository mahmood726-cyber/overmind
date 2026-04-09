# OVERMIND Daily Intelligence Report

**Day 1** | Generated: 2026-04-08T22:13:36+00:00

## Portfolio
- 516 projects | 285 testable | 178 advanced math
- Risk: {'high': 89, 'medium': 277, 'medium_high': 150}

## Verification Coverage
- **54/285 tested (18.9%)**
- High-risk unverified: 105
- Top unverified:
  - overmind (risk=high, math=20)
  - advanced-nma-pooling (risk=high, math=20)
  - DTA70 (risk=high, math=17)
  - Pairwise70 (risk=high, math=15)
  - rmstnma (risk=high, math=15)

## Regressions
- Active: 41
  - advanced-nma-pooling-6e3c8bdb: Nightly: advanced-nma-pooling REJECT
  - cardiooracle-6cb36757: Pass rate degraded: 16% -> 0%
  - cardiooracle-6cb36757: Nightly: CardioOracle FAIL
  - idea12-59249342: Nightly: idea12 FAIL
  - ipd-meta-pro-link-40520491: Nightly: ipd-meta-pro-link REJECT
  - dataextractor-9c5488b5: Nightly: Dataextractor_backup_20260114_110706 FAIL
  - evidence-inference-4c874004: Nightly: EvidenceOracle REJECT
  - cbamm-0820ec88: Nightly: Cbamm FAIL
  - dta70-4b170dbc: Nightly: DTA70 FAIL
  - ipd-qma-project-b5694da4: Nightly: ipd_qma_project REJECT

## Runner Performance
- codex: q=0.800 (W:3 L:0)
- gemini: q=0.667 (W:1 L:0)
- test_runner: q=0.664 (W:74 L:37)
- claude: q=0.391 (W:80 L:125)

## Memory
- 123 memories (avg relevance: 0.89)
- Types: {'audit_snapshot': 54, 'project_learning': 1, 'regression': 41, 'heuristic': 27}
- Heuristics: 27

## Today's Targets
- FIX 41 active regression(s) first
- Verify 5 projects from priority queue (coverage: 19%)
- Next project: overmind (priority=25)

## Priority Queue (next to verify)
1. **overmind** (priority=25, risk=high)
2. **DTA70** (priority=25, risk=high)
3. **Pairwise70** (priority=22, risk=high)
4. **rmstnma** (priority=22, risk=high)
5. **Pairwise70** (priority=22, risk=high)
6. **advanced-nma-pooling** (priority=22, risk=high)
7. **ctgov-search-strategies** (priority=22, risk=high)
8. **metasprint-dta** (priority=21, risk=high)
9. **Cbamm** (priority=20, risk=high)
10. **MLMResearch** (priority=18, risk=high)

## Benchmark Tracking (40-day proof)
- Coverage: 18.9%
- Pass rate: 49.4%
- Total verifications: 320
- Regressions found: 34
- Memories: 123
- Heuristics learned: 27
- Q-router entries: 4

## Session Mining (Claude Code transcript analysis)
- Sessions analyzed: 30
- Total messages: 7901
- Failure signals: 2056 | Success signals: 737
- Top errors: {'ImportError': 58, 'ValueError': 53, 'SyntaxError': 41, 'ModuleNotFoundError': 22, 'TypeError': 15, 'KeyError': 13, 'AssertionError': 8}
- Most active: user(29x), nightly_verify(6x), (6x), code_generator(4x), benford-law-enrollment-audit(2x)
- Insights mined: 3
