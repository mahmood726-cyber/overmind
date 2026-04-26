# Pairwise70

**Last verified:** 2026-04-26 02:40 UTC | **Verdict:** REJECT (Witnesses disagree: smoke, numerical_continuity PASS vs test_suite FAIL)
**Bundle hash:** 408a79b9bf5ff6e1 | **Risk:** high | **Math:** 15

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | FAIL | 120.0s | Timed out after 120s |
| smoke | PASS | 22.7s | 36 modules imported OK |
| numerical | SKIP | 0.0s | skipped |
| numerical_continuity | PASS | 0.0s | numerical continuity: baseline + provenance checks OK |

## Project

- **Path:** C:\Users\user\OneDrive - NHS\Documents\Pairwise70
- **Type:** hybrid_browser_analytics_app
- **Stack:** html, r
- **Test command:** `python -m pytest tests/selenium_comprehensive_test.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | FAIL | 2/3 | 3.5s | 8fb12b4c5515efbe |
| 2026-04-08 | FAIL | 2/3 | 8.2s | cec8002373305161 |
| 2026-04-09 | FAIL | 2/3 | 7.2s | a0fe00bcca841c59 |
| 2026-04-10 | FAIL | 2/3 | 4.3s | 45188bb4e02575e8 |
| 2026-04-11 | FAIL | 2/3 | 4.7s | 0b93ed9907e210c4 |
| 2026-04-12 | FAIL | 2/3 | 6.3s | 7a3c106bea091122 |
| 2026-04-13 | FAIL | 2/3 | 121.3s | bb3fc48447c5dedc |
| 2026-04-15 | FAIL | 1/1 | 0.0s | 2d779ebe57f08f5a |
| 2026-04-17 | REJECT | 2/3 | 136.2s | b8d110e4193a3169 |
| 2026-04-26 | REJECT | 3/4 | 142.7s | 408a79b9bf5ff6e1 |

## Notes

Witnesses disagree: smoke, numerical_continuity PASS vs test_suite FAIL

**test_suite:** Timed out after 120s
