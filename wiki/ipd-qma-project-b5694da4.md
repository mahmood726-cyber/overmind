# ipd_qma_project

**Last verified:** 2026-04-09 01:34 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs smoke FAIL)
**Bundle hash:** 1f0fa6928f88c397 | **Risk:** high | **Math:** 15

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 14.7s | ..........................................s.................             [100%]
 |
| smoke | FAIL | 60.3s | ipd_qma_bayesian: , in <module> |
| numerical | SKIP | 0.0s | skipped |

## Project

- **Path:** C:\Projects\ipd_qma_project
- **Type:** python_tool
- **Stack:** python
- **Test command:** `python -m pytest tests/test_ipd_qma.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | REJECT | 2/3 | 72.0s | c560c98377c7e3f8 |
| 2026-04-08 | REJECT | 2/3 | 32.4s | eb25bbf0a9bb54b2 |
| 2026-04-08 | REJECT | 2/3 | 52.3s | d2908cfa3d0f0027 |
| 2026-04-09 | REJECT | 2/3 | 75.0s | 1f0fa6928f88c397 |

## Notes

Witnesses disagree: test_suite PASS vs smoke FAIL

**smoke:** ipd_qma_bayesian: , in <module>
    import ipd_qma_bayesian
  File "C:\Projects\ipd_qma_project\ipd_qma_bayesian.py", line 418
    """
    ^
SyntaxError: unterminated triple-quoted string literal (det
