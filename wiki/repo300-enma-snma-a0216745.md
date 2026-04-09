# repo300-ENMA-SNMA

**Last verified:** 2026-04-09 01:34 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs smoke FAIL)
**Bundle hash:** d8c7b57cd398bafe | **Risk:** high | **Math:** 14

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 2.8s | .                                                                        [100%]
 |
| smoke | FAIL | 1.4s | R.01_data_audit_and_fix: File "<string>", line 1 |
| numerical | SKIP | 0.0s | skipped |

## Project

- **Path:** C:\Projects\repo300-ENMA-SNMA
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, r
- **Test command:** `python -m pytest tests/test_smoke.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | REJECT | 2/3 | 5.7s | b86fb37e121725ae |
| 2026-04-08 | REJECT | 2/3 | 3.4s | c916fce545b72e8f |
| 2026-04-08 | REJECT | 2/3 | 6.1s | fdd92540adc3644c |
| 2026-04-09 | REJECT | 2/3 | 4.2s | d8c7b57cd398bafe |

## Notes

Witnesses disagree: test_suite PASS vs smoke FAIL

**smoke:** R.01_data_audit_and_fix: File "<string>", line 1
    import R.01_data_audit_and_fix
               ^
SyntaxError: invalid decimal literal
R.03_simulation_engine: File "<string>", line 1
    import R.0
