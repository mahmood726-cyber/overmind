# truthcert-denominator-phase1

**Last verified:** 2026-04-13 02:18 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite, smoke PASS vs numerical FAIL)
**Bundle hash:** 875651b66d9d5623 | **Risk:** high | **Math:** 10

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 4.4s | .                                                                        [100%]
 |
| smoke | PASS | 16.5s | 14 modules imported OK |
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
| 2026-04-10 | REJECT | 3/3 | 31.2s | d36339bee79c105b |
| 2026-04-11 | REJECT | 3/3 | 23.9s | 4dd6b59869e16db5 |
| 2026-04-12 | REJECT | 3/3 | 22.7s | c808f3db46ed43ae |
| 2026-04-13 | REJECT | 3/3 | 20.9s | 875651b66d9d5623 |

## Notes

Witnesses disagree: test_suite, smoke PASS vs numerical FAIL

**numerical:** Failed to start: [WinError 2] The system cannot find the file specified
