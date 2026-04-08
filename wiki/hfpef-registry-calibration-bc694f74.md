# hfpef_registry_calibration

**Last verified:** 2026-04-08 23:40 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs smoke FAIL)
**Bundle hash:** c51ebe4913953e3e | **Risk:** high | **Math:** 6

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 4.2s | .                                                                        [100%]
 |
| smoke | FAIL | 3.4s | scripts.learn_gate:   File "C:\Projects\hfpef_registry_calibration\scripts\learn |

## Project

- **Path:** C:\Projects\hfpef_registry_calibration
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, javascript, python
- **Test command:** `python -m pytest tests/test_validation.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | REJECT | 2/2 | 6.0s | 8f92530f8b5a9ffc |
| 2026-04-08 | REJECT | 2/2 | 6.7s | 0d4c593a914f472f |
| 2026-04-08 | REJECT | 2/2 | 7.6s | c51ebe4913953e3e |

## Notes

Witnesses disagree: test_suite PASS vs smoke FAIL

**smoke:** scripts.learn_gate:   File "C:\Projects\hfpef_registry_calibration\scripts\learn_gate.py", line 6, in <module>
    from hfpef_calibrate.gate import run_gate_learning
ModuleNotFoundError: No module nam
