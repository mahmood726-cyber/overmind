# MetaAudit

**Last verified:** 2026-04-08 22:10 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs smoke FAIL)
**Bundle hash:** 2aed1c53e73c205c | **Risk:** high | **Math:** 7

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 5.3s | ============================= test session starts =============================
 |
| smoke | FAIL | 27.1s | sensitivity_analysis: import timed out |

## Project

- **Path:** C:\MetaAudit
- **Type:** python_tool
- **Stack:** python
- **Test command:** `python -m pytest -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | REJECT | 2/2 | 38.5s | 43a88aa9bcb94507 |
| 2026-04-08 | REJECT | 2/2 | 32.4s | 2aed1c53e73c205c |

## Notes

Witnesses disagree: test_suite PASS vs smoke FAIL

**smoke:** sensitivity_analysis: import timed out
