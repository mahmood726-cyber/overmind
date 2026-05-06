# superapp

**Last verified:** 2026-05-06 10:55 UTC | **Verdict:** REJECT (Witnesses disagree: smoke, semgrep, numerical_continuity PASS vs test_suite FAIL)
**Bundle hash:** 0bd7905cc12f54d2 | **Risk:** high | **Math:** 20

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | FAIL | 1089.9s | Timed out after 120s |
| smoke | PASS | 2.7s | 40 modules imported OK |
| semgrep | PASS | 29.6s | semgrep findings: ERROR=0 WARNING=0 INFO=0; engine errors=1 |
| pip_audit | SKIP | 0.0s | skipped |
| numerical | SKIP | 0.0s | skipped |
| numerical_continuity | PASS | 0.0s | numerical continuity: baseline + provenance checks OK |

## Project

- **Path:** C:\Projects\superapp
- **Type:** browser_app
- **Stack:** css, html, javascript
- **Test command:** `npm run test`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-05-05 | FAIL | 1/1 | 1800.0s | a4a66d73a7e1c6a0 |
| 2026-05-06 | REJECT | 4/6 | 1122.2s | 0bd7905cc12f54d2 |

## Notes

Witnesses disagree: smoke, semgrep, numerical_continuity PASS vs test_suite FAIL

**test_suite:** Timed out after 120s
