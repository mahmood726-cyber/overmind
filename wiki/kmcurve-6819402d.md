# KMcurve

**Last verified:** 2026-05-16 03:47 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite, semgrep, numerical, numerical_continuity PASS vs smoke FAIL)
**Bundle hash:** 8b798d42160267f4 | **Risk:** high | **Math:** 20

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 13.4s | ....                                                                     [100%]
 |
| smoke | FAIL | 96.6s | py:diagnose_multicurve_issue: import timed out |
| semgrep | PASS | 40.0s | semgrep findings: ERROR=0 WARNING=0 INFO=0; engine errors=0 |
| pip_audit | SKIP | 0.0s | skipped |
| numerical | PASS | 1.6s | 9 values within tolerance |
| numerical_continuity | PASS | 0.0s | numerical continuity: baseline + provenance checks OK |

## Project

- **Path:** C:\Projects\KMcurve
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, r
- **Test command:** `python -m pytest tests/test_pipeline_smoke.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-28 | UNVERIFIED | 3/4 | 90.6s | bf488203bdb3a9f6 |
| 2026-05-05 | REJECT | 4/6 | 90.7s | e07b41b8e35ea7c3 |
| 2026-05-05 | CERTIFIED | 5/6 | 96.6s | a49a71f4a78530ac |
| 2026-05-09 | CERTIFIED | 5/6 | 148.0s | 1b6b715af45b5881 |
| 2026-05-10 | CERTIFIED | 5/6 | 112.4s | a2505a2889e2dc28 |
| 2026-05-12 | CERTIFIED | 5/6 | 127.6s | 43e80030cbc32710 |
| 2026-05-13 | CERTIFIED | 5/6 | 141.9s | e2e5d1d8eb6ef71e |
| 2026-05-14 | CERTIFIED | 5/6 | 170.6s | 9163cc5bc5f245f5 |
| 2026-05-15 | CERTIFIED | 5/6 | 155.5s | 4febb14d8b8b69ef |
| 2026-05-16 | REJECT | 5/6 | 151.7s | 8b798d42160267f4 |

## Notes

Witnesses disagree: test_suite, semgrep, numerical, numerical_continuity PASS vs smoke FAIL

**smoke:** py:diagnose_multicurve_issue: import timed out
