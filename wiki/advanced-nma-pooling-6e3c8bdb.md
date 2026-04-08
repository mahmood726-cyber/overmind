# advanced-nma-pooling

**Last verified:** 2026-04-08 22:10 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite, smoke PASS vs numerical FAIL)
**Bundle hash:** 82b5f018ef023136 | **Risk:** high | **Math:** 20

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 3.7s | .                                                                        [100%]
 |
| smoke | PASS | 10.4s | 11 modules imported OK |
| numerical | FAIL | 0.0s | Blocked: command prefix not allowlisted: C:\Users\user\AppData\Local\Programs\Py |

## Project

- **Path:** C:\Models\advanced-nma-pooling
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest tests/simulation/test_smoke_simulation.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | CERTIFIED | 2/3 | 13.0s | 41a24fefa7938612 |
| 2026-04-08 | REJECT | 3/3 | 15.5s | b61ca40889166bd0 |
| 2026-04-08 | REJECT | 3/3 | 14.1s | 82b5f018ef023136 |

## Notes

Witnesses disagree: test_suite, smoke PASS vs numerical FAIL

**numerical:** Blocked: command prefix not allowlisted: C:\Users\user\AppData\Local\Programs\Python\Python313\python.exe C:\overmind\dat
