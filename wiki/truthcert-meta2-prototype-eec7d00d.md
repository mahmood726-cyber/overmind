# truthcert-meta2-prototype

**Last verified:** 2026-04-08 23:40 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs smoke FAIL)
**Bundle hash:** be92b083728eb7ec | **Risk:** high | **Math:** 8

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 7.5s | .                                                                        [100%]
 |
| smoke | FAIL | 85.5s | sim.run_suite: import timed out |

## Project

- **Path:** C:\Models\truthcert-meta2-prototype
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest tests/test_arbitration_conservative.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | CERTIFIED | 2/2 | 41.1s | ecfd42d6073b0aae |
| 2026-04-08 | CERTIFIED | 2/2 | 35.0s | 784989dcfcd832f6 |
| 2026-04-08 | REJECT | 2/2 | 93.0s | be92b083728eb7ec |

## Notes

Witnesses disagree: test_suite PASS vs smoke FAIL

**smoke:** sim.run_suite: import timed out
sim.score: import timed out
sim.selection: import timed out
