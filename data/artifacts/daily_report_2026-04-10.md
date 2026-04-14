# OVERMIND Daily Intelligence Report

**Day 1** | Generated: 2026-04-10T19:13:16+00:00

## Portfolio
- 603 projects | 316 testable | 215 advanced math
- Risk: {'medium': 318, 'medium_high': 188, 'high': 97}

## Verification Coverage
- **84/316 tested (26.6%)**
- High-risk unverified: 123
- Top unverified:
  - advanced-nma-pooling (risk=high, math=20)
  - DTA70 (risk=high, math=17)
  - Pairwise70 (risk=high, math=15)
  - Pairwise70 (risk=high, math=15)
  - rmstnma (risk=high, math=15)

## Regressions
- Active: 83
  - grma-paper-c4737385: Nightly: GRMA_paper FAIL
  - meta-ecosystem-model-3d6353ab: Pass rate degraded: 100% -> 0%
  - meta-ecosystem-model-3d6353ab: Nightly: Meta_Ecosystem_Model FAIL
  - metaaudit-b111c205: Nightly: MetaAudit REJECT
  - metaoverfit-5f64eb8f: Nightly: metaoverfit FAIL
  - mlmresearch-603c45f0: Nightly: MLMResearch FAIL
  - metaregression-b984b3aa: Nightly: MetaRegression REJECT
  - pub-bias-simulation-633c69de: Pass rate degraded: 50% -> 0%
  - pub-bias-simulation-633c69de: Nightly: pub-bias-simulation FAIL
  - componentnma-5d7f067c: Pass rate degraded: 100% -> 50%

## Runner Performance
- codex: q=0.800 (W:3 L:0)
- gemini: q=0.667 (W:1 L:0)
- test_runner: q=0.665 (W:112 L:56)
- claude: q=0.385 (W:148 L:237)

## Memory
- 196 memories (avg relevance: 0.58)
- Types: {'audit_snapshot': 84, 'project_learning': 1, 'heuristic': 28, 'regression': 83}
- Heuristics: 28

## Today's Targets
- FIX 83 active regression(s) first
- Verify 5 projects from priority queue (coverage: 27%)
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
10. **MLMResearch** (priority=18, risk=high)

## Benchmark Tracking (40-day proof)
- Coverage: 26.6%
- Pass rate: 47.4%
- Total verifications: 557
- Regressions found: 58
- Memories: 196
- Heuristics learned: 28
- Q-router entries: 4

## Session Mining (Claude Code transcript analysis)
- Sessions analyzed: 30
- Total messages: 12540
- Failure signals: 3442 | Success signals: 941
- Top errors: {'ValueError': 71, 'SyntaxError': 51, 'TypeError': 47, 'ImportError': 27, 'AssertionError': 17, 'KeyError': 14, 'ModuleNotFoundError': 7}
- Most active: (52x), user(22x), index(19x), nightly_verify(4x), bbxaihll6(2x)
- Insights mined: 3
