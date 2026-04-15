# Denominator_Calibrated_Living_NMA

**Last verified:** 2026-04-15 02:13 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs smoke FAIL)
**Bundle hash:** b545a6bbd5c440c7 | **Risk:** high | **Math:** 8

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 1.3s | ........                                                           [100%]
8 pass |
| smoke | FAIL | 1.7s | py:src.dclnma.witnesses.base: rt name 'WitnessContext' from partially initialize |

## Project

- **Path:** C:\Models\Denominator_Calibrated_Living_NMA
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, javascript, python
- **Test command:** `python -m pytest tests/test_smoke.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | PASS | 1/2 | 3.5s | c2ff2f48d354a0b0 |
| 2026-04-08 | PASS | 1/2 | 3.4s | 13255426320da027 |
| 2026-04-08 | PASS | 1/2 | 4.0s | 07ca5aa65eba3d3d |
| 2026-04-10 | PASS | 1/2 | 2.3s | 81077f9a8176f527 |
| 2026-04-11 | PASS | 1/2 | 2.2s | 4bda2c605c4c29d9 |
| 2026-04-12 | PASS | 1/2 | 2.0s | 00aea3833e8fc566 |
| 2026-04-13 | PASS | 1/2 | 2.0s | 756373b48b333aea |
| 2026-04-15 | REJECT | 2/2 | 3.0s | b545a6bbd5c440c7 |

## Notes

Witnesses disagree: test_suite PASS vs smoke FAIL

**smoke:** py:src.dclnma.witnesses.base: rt name 'WitnessContext' from partially initialized module 'src.dclnma.witnesses.base' (most likely due to a circular import) (C:\Models\Denominator_Calibrated_Living_NMA
