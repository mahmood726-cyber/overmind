# HTA_Evidence_Integrity_Suite

**Last verified:** 2026-05-10 02:59 UTC | **Verdict:** CERTIFIED (4/4 witnesses agree PASS)
**Bundle hash:** e91887c6597d6f71 | **Risk:** high | **Math:** 10

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 2.0s | .                                                                        [100%]
 |
| smoke | SKIP | 0.0s | skipped |
| semgrep | PASS | 74.1s | semgrep findings: ERROR=0 WARNING=0 INFO=0; engine errors=0 |
| pip_audit | SKIP | 0.0s | skipped |
| numerical | PASS | 0.1s | 9 values within tolerance |
| numerical_continuity | PASS | 0.0s | numerical continuity: baseline + provenance checks OK |

## Project

- **Path:** C:\Models\HTA_Evidence_Integrity_Suite
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python, r
- **Test command:** `python -m pytest tests/test_manuscript_numbers.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-05-05 | CERTIFIED | 4/6 | 101.3s | 900ea0d374865237 |
| 2026-05-09 | CERTIFIED | 4/6 | 93.6s | 76b1635b66329040 |
| 2026-05-10 | CERTIFIED | 4/6 | 76.2s | e91887c6597d6f71 |
