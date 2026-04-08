# MetaAudit

**Last verified:** 2026-04-08 23:40 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs smoke FAIL)
**Bundle hash:** 5b466dc7ad731256 | **Risk:** high | **Math:** 7

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 6.3s | ============================= test session starts =============================
 |
| smoke | FAIL | 33.1s | sensitivity_analysis: import timed out |

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

## Notes

Witnesses disagree: test_suite PASS vs smoke FAIL

**smoke:** sensitivity_analysis: import timed out
