# Finrenone

**Last verified:** 2026-05-04 17:46 UTC | **Verdict:** REJECT (Witnesses disagree: pip_audit, numerical_continuity PASS vs test_suite, smoke, semgrep FAIL)
**Bundle hash:** fe4d495237d25e20 | **Risk:** high | **Math:** 15

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | FAIL | 3.2s | s\user\AppData\Local\Programs\Python\Python313\Lib\site-packages\_pytest\main.py |
| smoke | FAIL | 40.2s | py:propagate_features:  |
| semgrep | FAIL | 73.9s | semgrep findings: ERROR=5 WARNING=31 INFO=0; engine errors=3 |
| pip_audit | PASS | 48.2s | pip-audit findings: 0 vulnerabilities across 17 dep(s); scope: requirements file |
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

## Notes

Witnesses disagree: pip_audit, numerical_continuity PASS vs test_suite, smoke, semgrep FAIL

**test_suite:** s\user\AppData\Local\Programs\Python\Python313\Lib\site-packages\_pytest\main.py", line 365, in pytest_cmdline_main
    return wrap_session(config, _main)
  File "C:\Users\user\AppData\Local\Programs\

**smoke:** py:propagate_features: 
py:serve_coop: import timed out

**semgrep:** semgrep findings: ERROR=5 WARNING=31 INFO=0; engine errors=3
blocking ERROR findings:
  - python.lang.security.use-defused-xml.use-defused-xml  scripts\find_correct_pmids.py:20
  - python.lang.securit
