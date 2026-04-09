# Pairwise70

**Last verified:** 2026-04-09 01:34 UTC | **Verdict:** FAIL (All witnesses FAIL: test_suite, smoke)
**Bundle hash:** a0fe00bcca841c59 | **Risk:** high | **Math:** 15

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | FAIL | 3.8s |  |
| smoke | FAIL | 3.4s | truthcert.setup: usage: -c [global_opts] cmd1 [cmd1_opts] [cmd2 [cmd2_opts] ...] |
| numerical | SKIP | 0.0s | skipped |

## Project

- **Path:** C:\Users\user\OneDrive - NHS\Documents\Pairwise70
- **Type:** hybrid_browser_analytics_app
- **Stack:** html, r
- **Test command:** `python -m pytest tests/selenium_comprehensive_test.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | FAIL | 2/3 | 6.3s | 6dba2b874dbfe913 |
| 2026-04-08 | FAIL | 2/3 | 3.5s | 8fb12b4c5515efbe |
| 2026-04-08 | FAIL | 2/3 | 8.2s | cec8002373305161 |
| 2026-04-09 | FAIL | 2/3 | 7.2s | a0fe00bcca841c59 |

## Notes

All witnesses FAIL: test_suite, smoke

**smoke:** truthcert.setup: usage: -c [global_opts] cmd1 [cmd1_opts] [cmd2 [cmd2_opts] ...]
   or: -c --help [cmd1 cmd2 ...]
   or: -c --help-commands
   or: -c cmd --help

error: no commands supplied
