# metasprint-autopilot

**Last verified:** 2026-05-04 21:18 UTC | **Verdict:** CERTIFIED (6/6 witnesses agree PASS)
**Bundle hash:** 5a30807619c0e114 | **Risk:** high | **Math:** 13

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 12.8s | ..                                                                       [100%]
 |
| smoke | PASS | 10.6s | 40 modules imported OK |
| semgrep | PASS | 44.4s | semgrep findings: ERROR=0 WARNING=3 INFO=0; engine errors=5
3 advisory WARNING f |
| pip_audit | PASS | 64.7s | pip-audit findings: 0 vulnerabilities across 24 dep(s); scope: requirements file |
| numerical | PASS | 0.2s | 7 values within tolerance |
| numerical_continuity | PASS | 0.0s | numerical continuity: baseline + provenance checks OK |

## Project

- **Path:** C:\Projects\metasprint-autopilot
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, playwright, python
- **Test command:** `python -m pytest tests/test_ui.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-05-04 | REJECT | 6/6 | 127.8s | 1c5d8227bc5191bf |
| 2026-05-04 | REJECT | 6/6 | 107.2s | aae6752fc1186f1f |
| 2026-05-04 | CERTIFIED | 6/6 | 132.8s | 5a30807619c0e114 |
