# Finrenone

**Last verified:** 2026-05-09 03:21 UTC | **Verdict:** REJECT (Witnesses disagree: smoke, pip_audit, numerical, numerical_continuity PASS vs semgrep FAIL)
**Bundle hash:** e408be710537d004 | **Risk:** high | **Math:** 15

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | SKIP | 24.2s | skipped |
| smoke | PASS | 20.2s | 40 modules imported OK |
| semgrep | FAIL | 154.7s | semgrep findings: ERROR=1 WARNING=36 INFO=0; engine errors=13 |
| pip_audit | PASS | 60.1s | pip-audit findings: 0 vulnerabilities across 17 dep(s); scope: requirements file |
| numerical | PASS | 0.1s | 5 values within tolerance |
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
| 2026-05-09 | REJECT | 5/6 | 259.4s | e408be710537d004 |

## Notes

Witnesses disagree: smoke, pip_audit, numerical, numerical_continuity PASS vs semgrep FAIL

**semgrep:** semgrep findings: ERROR=1 WARNING=36 INFO=0; engine errors=13
blocking ERROR findings:
  - python.lang.security.use-defused-xml.use-defused-xml  scripts\nct_databank_pmid_finder.py:26
36 advisory WARN
