# MetaAudit

**Last verified:** 2026-04-08 20:23 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs smoke FAIL)
**Bundle hash:** 43a88aa9bcb94507 | **Risk:** high | **Math:** 7

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 6.9s | ============================= test session starts =============================
 |
| smoke | FAIL | 31.7s | sensitivity_analysis: import timed out |

## Project

- **Path:** C:\MetaAudit
- **Type:** python_tool
- **Stack:** python
- **Test command:** `python -m pytest -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | REJECT | 2/2 | 38.5s | 43a88aa9bcb94507 |

## Notes

Witnesses disagree: test_suite PASS vs smoke FAIL

**smoke:** sensitivity_analysis: import timed out
