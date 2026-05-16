# SheafNMA

**Last verified:** 2026-05-16 03:47 UTC | **Verdict:** UNVERIFIED (4/4 witnesses PASS but numerical witness SKIPPED (baseline missing) — NOT a release pass (upgraded after retry))
**Bundle hash:** 62231cd69ad11cab | **Risk:** high | **Math:** 17

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 19.6s | .                                                                        [100%]
 |
| smoke | PASS | 11.3s | 10 modules imported OK |
| semgrep | PASS | 75.8s | semgrep findings: ERROR=0 WARNING=0 INFO=0; engine errors=4 |
| pip_audit | SKIP | 0.0s | skipped |
| numerical | SKIP | 0.0s | skipped |
| numerical_continuity | PASS | 0.5s | numerical continuity: baseline + provenance checks OK |

## Project

- **Path:** C:\Models\SheafNMA
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest tests/test_smoke.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-05-16 | UNVERIFIED | 4/6 | 107.3s | 62231cd69ad11cab |
