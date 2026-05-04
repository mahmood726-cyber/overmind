# ipd_qma_project

**Last verified:** 2026-05-04 15:00 UTC | **Verdict:** UNVERIFIED (5/5 witnesses PASS but numerical witness SKIPPED (baseline missing) — NOT a release pass)
**Bundle hash:** 3f784c3a1b9f1064 | **Risk:** high | **Math:** 15

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 6.8s | .......................................s....................             [100%]
 |
| smoke | PASS | 20.2s | 13 modules imported OK |
| semgrep | PASS | 14.7s | semgrep findings: ERROR=0 WARNING=0 INFO=0; engine errors=0 |
| pip_audit | PASS | 55.8s | pip-audit findings: 0 vulnerabilities across 54 dep(s); scope: requirements file |
| numerical | SKIP | 0.0s | skipped |
| numerical_continuity | PASS | 0.0s | numerical continuity: baseline + provenance checks OK |

## Project

- **Path:** C:\Projects\ipd_qma_project
- **Type:** python_tool
- **Stack:** python
- **Test command:** `python -m pytest tests/test_ipd_qma.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-13 | REJECT | 2/3 | 29.3s | 285ada80d04c4164 |
| 2026-04-15 | FAIL | 1/1 | 0.0s | 146682c83e99b67f |
| 2026-04-17 | UNVERIFIED | 2/3 | 19.5s | 45c6f60dc8ba15af |
| 2026-04-19 | UNVERIFIED | 2/3 | 19.8s | 8e66a5339210bbf9 |
| 2026-04-20 | UNVERIFIED | 3/4 | 21.7s | 4f14f3c09b15dce3 |
| 2026-04-25 | UNVERIFIED | 3/4 | 28.8s | 0c37d529620bf084 |
| 2026-04-26 | UNVERIFIED | 3/4 | 27.7s | d99662256bf8c14d |
| 2026-04-27 | UNVERIFIED | 3/4 | 32.4s | 284fed6d3396e49e |
| 2026-04-28 | UNVERIFIED | 3/4 | 27.8s | eb8789a9ee2b3dfc |
| 2026-05-04 | UNVERIFIED | 5/6 | 97.6s | 3f784c3a1b9f1064 |
