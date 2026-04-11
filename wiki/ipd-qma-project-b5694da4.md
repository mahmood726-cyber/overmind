# ipd_qma_project

**Last verified:** 2026-04-11 02:30 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs smoke FAIL)
**Bundle hash:** 7002f899c032f483 | **Risk:** high | **Math:** 15

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 5.9s | ..........................................s.................             [100%]
 |
| smoke | FAIL | 31.3s | ipd_qma_ml: ost recent call last): |
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
| 2026-04-10 | REJECT | 2/3 | 39.6s | cbee2ff0743724ef |
| 2026-04-11 | REJECT | 2/3 | 37.2s | 7002f899c032f483 |

## Notes

Witnesses disagree: test_suite PASS vs smoke FAIL

**smoke:** ipd_qma_ml: ost recent call last):
  File "<string>", line 1, in <module>
    import ipd_qma_ml
  File "C:\Projects\ipd_qma_project\ipd_qma_ml.py", line 1
    .asarray(treatment)
    ^
SyntaxError: in
