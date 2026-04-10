# MetaAudit

**Last verified:** 2026-04-10 02:33 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs smoke FAIL)
**Bundle hash:** 3cd39b074f1dddbb | **Risk:** high | **Math:** 7

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 5.1s | ============================= test session starts =============================
 |
| smoke | FAIL | 31.5s | sensitivity_analysis: import timed out |

## Project

- **Path:** C:\MetaAudit
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest tests/test_integration.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | REJECT | 2/2 | 38.5s | 43a88aa9bcb94507 |
| 2026-04-08 | REJECT | 2/2 | 32.4s | 2aed1c53e73c205c |
| 2026-04-08 | REJECT | 2/2 | 39.4s | 5b466dc7ad731256 |
| 2026-04-10 | REJECT | 2/2 | 36.6s | 3cd39b074f1dddbb |

## Notes

Witnesses disagree: test_suite PASS vs smoke FAIL

**smoke:** sensitivity_analysis: import timed out
