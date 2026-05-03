# hfpef_registry_calibration

**Last verified:** 2026-05-03 12:38 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite, smoke PASS vs semgrep FAIL)
**Bundle hash:** ff7a54387852c2fb | **Risk:** high | **Math:** 6

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 3.1s | .                                                                        [100%]
 |
| smoke | PASS | 26.2s | 36 modules imported OK |
| semgrep | FAIL | 40.8s | semgrep findings: ERROR=1 WARNING=3 INFO=0; engine errors=41 |
| pip_audit | SKIP | 0.0s | skipped |

## Project

- **Path:** C:\Projects\hfpef_registry_calibration
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, javascript, python
- **Test command:** `python -m pytest tests/test_validation.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-13 | PASS | 1/2 | 2.5s | dbaaf63358c37293 |
| 2026-04-15 | CERTIFIED | 2/2 | 20.3s | f4d2de5610d934e3 |
| 2026-04-17 | CERTIFIED | 2/2 | 23.7s | 65cf6396764f71c0 |
| 2026-04-19 | CERTIFIED | 2/2 | 22.2s | 5d6f4c68442430c5 |
| 2026-04-20 | CERTIFIED | 2/2 | 23.2s | 367b5edc095d4f74 |
| 2026-04-25 | CERTIFIED | 2/2 | 29.5s | eb1b540aad04e809 |
| 2026-04-26 | CERTIFIED | 2/2 | 32.5s | 009023cc0d6751d1 |
| 2026-04-27 | CERTIFIED | 2/2 | 36.1s | 627717fe7753e63c |
| 2026-04-28 | CERTIFIED | 2/2 | 33.9s | ef43dddf91ae05ec |
| 2026-05-03 | REJECT | 3/4 | 70.1s | ff7a54387852c2fb |

## Notes

Witnesses disagree: test_suite, smoke PASS vs semgrep FAIL

**semgrep:** semgrep findings: ERROR=1 WARNING=3 INFO=0; engine errors=41
blocking ERROR findings:
  - python.lang.security.use-defused-xml.use-defused-xml  src\hfpef_calibrate\pubmed.py:6
3 advisory WARNING findi
