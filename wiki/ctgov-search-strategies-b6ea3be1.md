# ctgov-search-strategies

**Last verified:** 2026-05-03 12:38 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite, smoke, pip_audit PASS vs semgrep FAIL)
**Bundle hash:** 1e63b39f7cedb825 | **Risk:** high | **Math:** 7

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 5.0s | ............................                                             [100%]
 |
| smoke | PASS | 18.4s | 40 modules imported OK |
| semgrep | FAIL | 60.9s | semgrep findings: ERROR=13 WARNING=7 INFO=0; engine errors=1 |
| pip_audit | PASS | 59.2s | pip-audit findings: 0 vulnerabilities across 51 dep(s); scope: requirements file |

## Project

- **Path:** C:\Projects\ctgov-analyses\ctgov-search-strategies
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `pytest tests/test_strategy_optimizer.py`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-13 | CERTIFIED | 2/2 | 12.6s | 43c90ae7a2559ddc |
| 2026-04-15 | CERTIFIED | 2/2 | 16.4s | 25ffa71963fa19b5 |
| 2026-04-17 | CERTIFIED | 2/2 | 18.4s | dbc950ebada82f0b |
| 2026-04-19 | CERTIFIED | 2/2 | 19.4s | 67cc639d353b8661 |
| 2026-04-20 | CERTIFIED | 2/2 | 18.6s | 512158da7d1d9278 |
| 2026-04-25 | CERTIFIED | 2/2 | 24.7s | 9509c4f59a0e365c |
| 2026-04-26 | CERTIFIED | 2/2 | 25.7s | ac917354d36ad125 |
| 2026-04-27 | CERTIFIED | 2/2 | 28.6s | 2e075ee5af4ece8e |
| 2026-04-28 | CERTIFIED | 2/2 | 23.1s | 2abc1f0b460b7654 |
| 2026-05-03 | REJECT | 4/4 | 143.5s | 1e63b39f7cedb825 |

## Notes

Witnesses disagree: test_suite, smoke, pip_audit PASS vs semgrep FAIL

**semgrep:** semgrep findings: ERROR=13 WARNING=7 INFO=0; engine errors=1
blocking ERROR findings:
  - python.lang.security.use-defused-xml.use-defused-xml  combined_search.py:15
  - python.lang.security.use-defus
