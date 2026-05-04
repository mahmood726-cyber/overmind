# arac

**Last verified:** 2026-05-04 17:46 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite, smoke PASS vs semgrep FAIL)
**Bundle hash:** 70bde19c0dc5bb6d | **Risk:** high | **Math:** 7

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 5.6s | .......                                                                  [100%]
 |
| smoke | PASS | 37.2s | 40 modules imported OK |
| semgrep | FAIL | 15.0s | semgrep findings: ERROR=1 WARNING=0 INFO=0; engine errors=0 |
| pip_audit | SKIP | 0.0s | skipped |

## Project

- **Path:** C:\Projects\arac
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, javascript, python
- **Test command:** `python -m pytest tests/test_repool_smoke.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-05-04 | REJECT | 3/4 | 57.8s | 70bde19c0dc5bb6d |

## Notes

Witnesses disagree: test_suite, smoke PASS vs semgrep FAIL

**semgrep:** semgrep findings: ERROR=1 WARNING=0 INFO=0; engine errors=0
blocking ERROR findings:
  - python.lang.security.use-defused-xml.use-defused-xml  src\arac\resolve\pubmed.py:28
