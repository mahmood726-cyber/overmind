# hfpef_registry_calibration

**Last verified:** 2026-04-08 20:23 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs smoke FAIL)
**Bundle hash:** 8f92530f8b5a9ffc | **Risk:** high | **Math:** 6

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 3.4s | .                                                                        [100%]
 |
| smoke | FAIL | 2.6s | scripts.learn_gate:   File "C:\Projects\hfpef_registry_calibration\scripts\learn |

## Project

- **Path:** C:\Projects\hfpef_registry_calibration
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, javascript, python
- **Test command:** `python -m pytest tests/test_validation.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | REJECT | 2/2 | 6.0s | 8f92530f8b5a9ffc |

## Notes

Witnesses disagree: test_suite PASS vs smoke FAIL

**smoke:** scripts.learn_gate:   File "C:\Projects\hfpef_registry_calibration\scripts\learn_gate.py", line 6, in <module>
    from hfpef_calibrate.gate import run_gate_learning
ModuleNotFoundError: No module nam
