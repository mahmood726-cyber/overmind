# Finrenone

**Last verified:** 2026-05-05 15:46 UTC | **Verdict:** UNVERIFIED (4/4 witnesses PASS but numerical witness SKIPPED (baseline missing) — NOT a release pass)
**Bundle hash:** e729b30cb1198305 | **Risk:** high | **Math:** 15

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | SKIP | 2.1s | skipped |
| smoke | PASS | 8.7s | 40 modules imported OK |
| semgrep | PASS | 42.9s | semgrep findings: ERROR=0 WARNING=31 INFO=0; engine errors=2
31 advisory WARNING |
| pip_audit | PASS | 33.2s | pip-audit findings: 0 vulnerabilities across 17 dep(s); scope: requirements file |
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
