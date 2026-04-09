# OVERMIND Daily Intelligence Report

**Day 1** | Generated: 2026-04-09T10:00:03+00:00

## Portfolio
- 643 projects | 346 testable | 259 advanced math
- Risk: {'high': 136, 'medium_high': 197, 'medium': 310}

## Verification Coverage
- **83/346 tested (24.0%)**
- High-risk unverified: 126
- Top unverified:
  - advanced-nma-pooling (risk=high, math=20)
  - DTA70 (risk=high, math=17)
  - Pairwise70 (risk=high, math=15)
  - rmstnma (risk=high, math=15)
  - Pairwise70 (risk=high, math=15)

## Regressions
- Active: 69
  - cbamm-0820ec88: Nightly: Cbamm FAIL
  - dta70-4b170dbc: Nightly: DTA70 FAIL
  - ipd-qma-project-b5694da4: Nightly: ipd_qma_project REJECT
  - pairwise70-5049aa49: Nightly: Pairwise70 FAIL
  - rmstnma-1810584a: Nightly: rmstnma FAIL
  - globalst-5d1477cf: Nightly: globalst FAIL
  - hfpef-registry-synth-65970c56: Pass rate degraded: 67% -> 33%
  - repo300-enma-snma-a0216745: Nightly: repo300-ENMA-SNMA REJECT
  - asreview-5star-e9fe8316: Nightly: asreview_5star REJECT
  - fatiha-project-930cf9dd: Nightly: FATIHA_Project FAIL

## Runner Performance
- codex: q=0.800 (W:3 L:0)
- gemini: q=0.667 (W:1 L:0)
- test_runner: q=0.664 (W:82 L:41)
- claude: q=0.386 (W:129 L:206)

## Memory
- 179 memories (avg relevance: 0.85)
- Types: {'audit_snapshot': 83, 'project_learning': 1, 'regression': 69, 'heuristic': 26}
- Heuristics: 26

## Today's Targets
- FIX 69 active regression(s) first
- Verify 5 projects from priority queue (coverage: 24%)
- Next project: DTA70 (priority=25)

## Priority Queue (next to verify)
1. **DTA70** (priority=25, risk=high)
2. **Pairwise70** (priority=22, risk=high)
3. **rmstnma** (priority=22, risk=high)
4. **Pairwise70** (priority=22, risk=high)
5. **advanced-nma-pooling** (priority=22, risk=high)
6. **Pairwise70** (priority=22, risk=high)
7. **ctgov-search-strategies** (priority=22, risk=high)
8. **metasprint-dta** (priority=21, risk=high)
9. **Denominator_Calibrated_Living_NMA** (priority=20, risk=high)
10. **Cbamm** (priority=20, risk=high)

## Benchmark Tracking (40-day proof)
- Coverage: 24.0%
- Pass rate: 46.5%
- Total verifications: 462
- Regressions found: 53
- Memories: 179
- Heuristics learned: 26
- Q-router entries: 4

## Session Mining (Claude Code transcript analysis)
- Sessions analyzed: 30
- Total messages: 8222
- Failure signals: 2205 | Success signals: 744
- Top errors: {'SyntaxError': 54, 'ValueError': 53, 'ImportError': 46, 'TypeError': 21, 'ModuleNotFoundError': 14, 'KeyError': 13, 'AssertionError': 9}
- Most active: (58x), user(30x), index(19x), nightly_verify(6x), code_generator(4x)
- Insights mined: 3
