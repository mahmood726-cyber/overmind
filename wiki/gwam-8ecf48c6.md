# GWAM

**Last verified:** 2026-05-03 12:38 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite, smoke PASS vs semgrep, pip_audit FAIL)
**Bundle hash:** 6df2b8a6e0cd15c4 | **Risk:** high | **Math:** 7

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 7.9s | ...........                                                              [100%]
 |
| smoke | PASS | 2.8s | 2 modules imported OK |
| semgrep | FAIL | 21.4s | semgrep findings: ERROR=1 WARNING=0 INFO=0; engine errors=0 |
| pip_audit | FAIL | 40.3s | pip-audit findings: 1 vulnerability across 26 dep(s); scope: requirements file:  |

## Project

- **Path:** C:\Models\GWAM
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest tests/test_bayesian_gwam.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-13 | PASS | 1/2 | 11.7s | aba95b8ce034d2e5 |
| 2026-04-15 | CERTIFIED | 2/2 | 7.9s | d935a3736e35e23e |
| 2026-04-17 | CERTIFIED | 2/2 | 9.6s | 88b1339ef862aad7 |
| 2026-04-19 | CERTIFIED | 2/2 | 9.3s | 02dc6d60465d20bc |
| 2026-04-20 | CERTIFIED | 2/2 | 9.3s | b4ab6d8d1a3b442c |
| 2026-04-25 | CERTIFIED | 2/2 | 12.3s | c5b6d73a3294c6b0 |
| 2026-04-26 | CERTIFIED | 2/2 | 13.3s | 063816ac50087122 |
| 2026-04-27 | CERTIFIED | 2/2 | 14.8s | 744fdcf26fa838f7 |
| 2026-04-28 | CERTIFIED | 2/2 | 13.5s | b1d9c5616a547fee |
| 2026-05-03 | REJECT | 4/4 | 72.3s | 6df2b8a6e0cd15c4 |

## Notes

Witnesses disagree: test_suite, smoke PASS vs semgrep, pip_audit FAIL

**semgrep:** semgrep findings: ERROR=1 WARNING=0 INFO=0; engine errors=0
blocking ERROR findings:
  - python.lang.security.use-defused-xml.use-defused-xml  scripts\build_pairwise70_ctgov_linkage_summary.py:32

**pip_audit:** pip-audit findings: 1 vulnerability across 26 dep(s); scope: requirements file: requirements.txt
vulnerable packages:
  - requests 2.32.5  CVE-2026-25645
fix: review pip-audit output, bump affected ve
