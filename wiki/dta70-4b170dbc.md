# DTA70

**Last verified:** 2026-04-17 02:44 UTC | **Verdict:** REJECT (Witnesses disagree: smoke PASS vs test_suite FAIL)
**Bundle hash:** 435a506375aa87c1 | **Risk:** high | **Math:** 17

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | FAIL | 1.0s | Error: Test failures |
| smoke | PASS | 0.1s | 1 modules imported OK |
| numerical | SKIP | 0.0s | skipped |

## Project

- **Path:** C:\Users\user\OneDrive - NHS\Documents\DTA70
- **Type:** hybrid_browser_analytics_app
- **Stack:** html, r
- **Test command:** `Rscript -e "testthat::test_dir('tests/testthat')"`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | FAIL | 1/3 | 0.0s | a3b46f1230268b7b |
| 2026-04-08 | FAIL | 1/3 | 0.0s | a4a459e2631835f6 |
| 2026-04-08 | FAIL | 1/3 | 0.0s | bbf82e7484a13bc1 |
| 2026-04-09 | FAIL | 1/3 | 0.0s | c52cdea3dc1182ff |
| 2026-04-10 | FAIL | 1/3 | 0.0s | 20722b476f7c290a |
| 2026-04-11 | FAIL | 1/3 | 0.0s | 1c75df3bdd9be90a |
| 2026-04-12 | FAIL | 1/3 | 0.0s | a39ba4961d62df30 |
| 2026-04-13 | FAIL | 1/3 | 0.0s | 0fda4fe619908f84 |
| 2026-04-15 | FAIL | 1/1 | 0.0s | c7e5e2376fd42c62 |
| 2026-04-17 | REJECT | 2/3 | 1.1s | 435a506375aa87c1 |

## Notes

Witnesses disagree: smoke PASS vs test_suite FAIL

**test_suite:** Error: Test failures
Execution halted

