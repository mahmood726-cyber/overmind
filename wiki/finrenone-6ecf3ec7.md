# Finrenone

**Last verified:** 2026-05-05 16:01 UTC | **Verdict:** REJECT (Witnesses disagree: semgrep, pip_audit, numerical_continuity PASS vs test_suite, smoke FAIL)
**Bundle hash:** eb9aa880179cad90 | **Risk:** high | **Math:** 15

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | FAIL | 3.7s |  |
| smoke | FAIL | 56.0s | py:fix_lightmode_contrast: import timed out |
| semgrep | PASS | 68.2s | semgrep findings: ERROR=0 WARNING=31 INFO=0; engine errors=5
31 advisory WARNING |
| pip_audit | PASS | 44.7s | pip-audit findings: 0 vulnerabilities across 17 dep(s); scope: requirements file |
| numerical | SKIP | 0.0s | skipped |
| numerical_continuity | PASS | 0.0s | numerical continuity: baseline + provenance checks OK |

## Project

- **Path:** C:\Projects\Finrenone
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-05-04 | REJECT | 5/6 | 165.5s | fe4d495237d25e20 |
| 2026-05-04 | REJECT | 5/6 | 152.2s | 0d4e592ccb31e213 |
| 2026-05-05 | UNVERIFIED | 4/6 | 86.9s | e729b30cb1198305 |
| 2026-05-05 | CERTIFIED | 5/6 | 90.2s | c9fb5967c8ee6097 |
| 2026-05-05 | REJECT | 5/6 | 172.5s | eb9aa880179cad90 |

## Notes

Witnesses disagree: semgrep, pip_audit, numerical_continuity PASS vs test_suite, smoke FAIL

**smoke:** py:fix_lightmode_contrast: import timed out
py:fix_review_issues: import timed out
py:improve_methodological: import timed out
py:serve_coop: import timed out
