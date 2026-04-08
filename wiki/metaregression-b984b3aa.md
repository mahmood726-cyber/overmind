# MetaRegression

**Last verified:** 2026-04-08 23:40 UTC | **Verdict:** REJECT (Witnesses disagree: smoke PASS vs test_suite FAIL)
**Bundle hash:** 1f12d2e833fe7d13 | **Risk:** medium_high | **Math:** 8

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | FAIL | 3.5s | s\user\AppData\Local\Programs\Python\Python313\Lib\site-packages\_pytest\main.py |
| smoke | PASS | 1.1s | 1 modules imported OK |

## Project

- **Path:** C:\Models\MetaRegression
- **Type:** browser_app
- **Stack:** css, html, javascript
- **Test command:** `python -m pytest tests/test_metaregression.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | REJECT | 2/2 | 3.3s | 54c3f3b4fcee603b |
| 2026-04-08 | REJECT | 2/2 | 3.1s | 7ac0dafc4767d32b |
| 2026-04-08 | REJECT | 2/2 | 4.6s | 1f12d2e833fe7d13 |

## Notes

Witnesses disagree: smoke PASS vs test_suite FAIL

**test_suite:** s\user\AppData\Local\Programs\Python\Python313\Lib\site-packages\_pytest\main.py", line 365, in pytest_cmdline_main
    return wrap_session(config, _main)
  File "C:\Users\user\AppData\Local\Programs\
