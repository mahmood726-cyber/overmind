# OVERMIND Daily Intelligence Report

**Day 1** | Generated: 2026-04-07T22:09:44+00:00

## Portfolio
- 495 projects | 275 testable | 173 advanced math
- Risk: {'medium_high': 146, 'high': 86, 'medium': 263}

## Verification Coverage
- **18/275 tested (6.5%)**
- High-risk unverified: 134
- Top unverified:
  - superapp (risk=high, math=20)
  - metasprint-autopilot (risk=high, math=20)
  - idea12 (risk=high, math=20)
  - ipd-meta-pro-link (risk=high, math=20)
  - advanced-nma-pooling (risk=high, math=20)

## Regressions
- Active: 8
  - openpalp-evidence-be0f7939: Verification failed
  - pairwise70-5049aa49: Verification failed
  - rmstnma-1810584a: Verification failed
  - dta70-4b170dbc: Verification failed
  - cbamm-0820ec88: Verification failed
  - meta-ecosystem-model-3d6353ab: Verification failed
  - pairwise70-900619fe: Verification failed
  - bayesianma-240f4a74: Pass rate degraded: 100% -> 50%

## Runner Performance
- codex: q=0.800 (W:3 L:0)
- claude: q=0.714 (W:4 L:1)
- gemini: q=0.667 (W:1 L:0)
- test_runner: q=0.662 (W:42 L:21)

## Memory
- 41 memories (avg relevance: 0.30)
- Types: {'audit_snapshot': 18, 'project_learning': 11, 'heuristic': 4, 'regression': 8}
- Heuristics: 4

## Today's Targets
- FIX 8 active regression(s) first
- Verify 10 high-priority projects (coverage: 6% -> ~10%)
- Next project: EvidenceOracle (priority=25)

## Priority Queue (next to verify)
1. **EvidenceOracle** (priority=25, risk=high)
2. **metasprint-autopilot** (priority=25, risk=high)
3. **truthcert-meta2-prototype** (priority=23, risk=high)
4. **FATIHA_Project** (priority=22, risk=high)
5. **HTA_Evidence_Integrity_Suite** (priority=22, risk=high)
6. **registry_first_rct_meta** (priority=22, risk=high)
7. **superapp** (priority=22, risk=high)
8. **rct-extractor-v2** (priority=22, risk=high)
9. **Pairwise70** (priority=22, risk=high)
10. **lec_phase0_bundle** (priority=22, risk=high)

## Benchmark Tracking (40-day proof)
- Coverage: 6.5%
- Pass rate: 69.4%
- Total verifications: 72
- Regressions found: 8
- Memories: 41
- Heuristics learned: 4
- Q-router entries: 4

## Session Mining (Claude Code transcript analysis)
- Sessions analyzed: 30
- Total messages: 15794
- Failure signals: 3188 | Success signals: 1568
- Top errors: {'ValueError': 183, 'KeyError': 61, 'ImportError': 46, 'TypeError': 44, 'SyntaxError': 42, 'AssertionError': 36, 'ModuleNotFoundError': 35}
- Most active: (42x), HTML(13x), stats_engine(10x), test_stats(10x), manuscript(6x)
- Insights mined: 3
