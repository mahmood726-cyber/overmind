# Finrenone

**Last verified:** 2026-05-15 07:13 UTC | **Verdict:** REJECT (Witnesses disagree: pip_audit, numerical, numerical_continuity PASS vs test_suite, smoke, semgrep FAIL)
**Bundle hash:** 614255d08c57d706 | **Risk:** high | **Math:** 15

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | FAIL | 27.8s | s\user\AppData\Local\Programs\Python\Python313\Lib\site-packages\_pytest\main.py |
| smoke | FAIL | 24.1s | py:improve_round2: import timed out |
| semgrep | FAIL | 261.8s | semgrep findings: ERROR=12 WARNING=47 INFO=0; engine errors=5 |
| pip_audit | PASS | 53.0s | pip-audit findings: 0 vulnerabilities across 17 dep(s); scope: requirements file |
| numerical | PASS | 0.2s | 5 values within tolerance |
| numerical_continuity | PASS | 0.0s | numerical continuity: baseline + provenance checks OK |

## Project

- **Path:** C:\Projects\Finrenone
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-05-04 | REJECT | 5/6 | 152.2s | 0d4e592ccb31e213 |
| 2026-05-05 | UNVERIFIED | 4/6 | 86.9s | e729b30cb1198305 |
| 2026-05-05 | CERTIFIED | 5/6 | 90.2s | c9fb5967c8ee6097 |
| 2026-05-05 | REJECT | 5/6 | 172.5s | eb9aa880179cad90 |
| 2026-05-09 | REJECT | 5/6 | 259.4s | e408be710537d004 |
| 2026-05-10 | REJECT | 5/6 | 154.8s | 2075f7ca193c41e2 |
| 2026-05-12 | REJECT | 5/6 | 194.3s | 68c251521869c9d2 |
| 2026-05-13 | REJECT | 5/6 | 233.8s | a7519e093676a2c9 |
| 2026-05-14 | REJECT | 6/6 | 303.1s | ec888ed8e2ff266d |
| 2026-05-15 | REJECT | 6/6 | 366.9s | 614255d08c57d706 |

## Notes

Witnesses disagree: pip_audit, numerical, numerical_continuity PASS vs test_suite, smoke, semgrep FAIL

**test_suite:** s\user\AppData\Local\Programs\Python\Python313\Lib\site-packages\_pytest\main.py", line 365, in pytest_cmdline_main
    return wrap_session(config, _main)
  File "C:\Users\user\AppData\Local\Programs\

**smoke:** py:improve_round2: import timed out

**semgrep:** semgrep findings: ERROR=12 WARNING=47 INFO=0; engine errors=5
blocking ERROR findings:
  - python.lang.security.use-defused-xml.use-defused-xml  scripts\add_topic_audit_first.py:173
  - python.lang.se
