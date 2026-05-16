# allmeta-pilot

**Last verified:** 2026-05-16 03:47 UTC | **Verdict:** REJECT (Witnesses disagree: smoke, semgrep, numerical_continuity PASS vs test_suite FAIL)
**Bundle hash:** 0590e8b3558b34ec | **Risk:** high | **Math:** 10

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | FAIL | 0.5s |  |
| smoke | PASS | 2.2s | 40 modules imported OK |
| semgrep | PASS | 10.4s | semgrep findings: ERROR=0 WARNING=0 INFO=0; engine errors=0 |
| pip_audit | SKIP | 0.0s | skipped |
| numerical | SKIP | 0.0s | skipped |
| numerical_continuity | PASS | 0.0s | numerical continuity: baseline + provenance checks OK |

## Project

- **Path:** C:\Users\user\Downloads\allmeta-pilot
- **Type:** browser_app
- **Stack:** html, javascript, playwright
- **Test command:** `npm run test`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-05-16 | REJECT | 4/6 | 13.1s | 0590e8b3558b34ec |

## Notes

Witnesses disagree: smoke, semgrep, numerical_continuity PASS vs test_suite FAIL
