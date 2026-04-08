# truthcert-denominator-phase1

**Last verified:** 2026-04-08 23:40 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite, smoke PASS vs numerical FAIL)
**Bundle hash:** 6f499d69c897aa81 | **Risk:** high | **Math:** 10

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 6.8s | .                                                                        [100%]
 |
| smoke | PASS | 33.7s | 14 modules imported OK |
| numerical | FAIL | 0.0s | Failed to start: [WinError 2] The system cannot find the file specified |

## Project

- **Path:** C:\Models\truthcert-denominator-phase1
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest tests/test_posterior_validity.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | REJECT | 3/3 | 38.8s | f1306a481e9bc540 |
| 2026-04-08 | REJECT | 3/3 | 30.1s | 5b92d181ddea281e |
| 2026-04-08 | REJECT | 3/3 | 40.5s | 6f499d69c897aa81 |

## Notes

Witnesses disagree: test_suite, smoke PASS vs numerical FAIL

**numerical:** Failed to start: [WinError 2] The system cannot find the file specified
