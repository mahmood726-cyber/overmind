# EvidenceOracle

**Last verified:** 2026-04-09 01:34 UTC | **Verdict:** REJECT (Witnesses disagree: smoke PASS vs test_suite FAIL)
**Bundle hash:** 956e79f678e86669 | **Risk:** high | **Math:** 14

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | FAIL | 5.2s | s\user\AppData\Local\Programs\Python\Python313\Lib\site-packages\_pytest\main.py |
| smoke | PASS | 8.8s | 2 modules imported OK |
| numerical | SKIP | 0.0s | skipped |

## Project

- **Path:** C:\Models\EvidenceOracle
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest tests/test_oracle.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | REJECT | 2/3 | 10.2s | c8971f1475e4fb4e |
| 2026-04-08 | REJECT | 2/3 | 6.5s | c1ecae7c507baea4 |
| 2026-04-08 | REJECT | 2/3 | 9.5s | 44df63bde770eda3 |
| 2026-04-09 | REJECT | 2/3 | 14.0s | 956e79f678e86669 |

## Notes

Witnesses disagree: smoke PASS vs test_suite FAIL

**test_suite:** s\user\AppData\Local\Programs\Python\Python313\Lib\site-packages\_pytest\main.py", line 365, in pytest_cmdline_main
    return wrap_session(config, _main)
  File "C:\Users\user\AppData\Local\Programs\
