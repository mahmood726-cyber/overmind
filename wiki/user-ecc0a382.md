# user

**Last verified:** 2026-04-19 02:36 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs smoke FAIL)
**Bundle hash:** 659993633edf0a0f | **Risk:** high | **Math:** 14

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 1.8s | .                                                                        [100%]
 |
| smoke | FAIL | 9.1s | py:AppData.Local.Programs.Python.Python313.Lib.asyncio.unix_events: rograms\Pyth |
| numerical | SKIP | 0.0s | skipped |

## Project

- **Path:** C:\Users\user
- **Type:** browser_app
- **Stack:** css, html, javascript
- **Test command:** `python -m pytest tests/test_integrity.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-17 | FAIL | 1/1 | 300.0s | 1055f3b1a5c66332 |
| 2026-04-19 | REJECT | 2/3 | 10.9s | 659993633edf0a0f |

## Notes

Witnesses disagree: test_suite PASS vs smoke FAIL

**smoke:** py:AppData.Local.Programs.Python.Python313.Lib.asyncio.unix_events: rograms\Python\Python313\Lib\asyncio\unix_events.py", line 40, in <module>
    raise ImportError('Signals are not really supported o
