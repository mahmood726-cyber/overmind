# MetaRegression

**Last verified:** 2026-04-08 22:10 UTC | **Verdict:** REJECT (Witnesses disagree: smoke PASS vs test_suite FAIL)
**Bundle hash:** 7ac0dafc4767d32b | **Risk:** medium_high | **Math:** 8

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | FAIL | 2.6s | s\user\AppData\Local\Programs\Python\Python313\Lib\site-packages\_pytest\main.py |
| smoke | PASS | 0.5s | 1 modules imported OK |

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

## Notes

Witnesses disagree: smoke PASS vs test_suite FAIL

**test_suite:** s\user\AppData\Local\Programs\Python\Python313\Lib\site-packages\_pytest\main.py", line 365, in pytest_cmdline_main
    return wrap_session(config, _main)
  File "C:\Users\user\AppData\Local\Programs\
