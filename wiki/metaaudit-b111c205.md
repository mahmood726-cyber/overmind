# MetaAudit

**Last verified:** 2026-05-16 03:47 UTC | **Verdict:** CERTIFIED (6/6 witnesses agree PASS (upgraded after retry))
**Bundle hash:** 2e6a7e9c90a92a06 | **Risk:** high | **Math:** 10

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 4.1s | ============================= test session starts =============================
 |
| smoke | PASS | 32.9s | 25 modules imported OK |
| semgrep | PASS | 44.3s | semgrep findings: ERROR=0 WARNING=0 INFO=0; engine errors=0 |
| pip_audit | PASS | 33.7s | pip-audit findings: 0 vulnerabilities across 12 dep(s); scope: requirements file |
| numerical | PASS | 1.8s | 4 values within tolerance |
| numerical_continuity | PASS | 0.0s | numerical continuity: baseline + provenance checks OK |

## Project

- **Path:** C:\MetaAudit
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest tests/test_integration.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-26 | CERTIFIED | 4/4 | 53.9s | 6e37aed10aecb352 |
| 2026-04-27 | CERTIFIED | 4/4 | 59.7s | dd365e6aedb3f45c |
| 2026-04-28 | CERTIFIED | 4/4 | 56.2s | 7eb894ed1bd9b176 |
| 2026-05-09 | CERTIFIED | 6/6 | 122.3s | 2380c2d449b8957f |
| 2026-05-10 | CERTIFIED | 6/6 | 90.1s | 990e9714dad25391 |
| 2026-05-12 | CERTIFIED | 6/6 | 116.4s | fb9faa3fb1c1dc25 |
| 2026-05-13 | CERTIFIED | 6/6 | 122.1s | b98667b76af9a722 |
| 2026-05-14 | CERTIFIED | 6/6 | 153.4s | 4baedc6c1116743f |
| 2026-05-15 | CERTIFIED | 6/6 | 133.8s | 4d732d2c0b4ac216 |
| 2026-05-16 | CERTIFIED | 6/6 | 116.8s | 2e6a7e9c90a92a06 |
