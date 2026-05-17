# Finrenone

**Last verified:** 2026-05-17 03:13 UTC | **Verdict:** REJECT (Witnesses disagree: pip_audit, numerical, numerical_continuity PASS vs test_suite, smoke, semgrep FAIL)
**Bundle hash:** e75ad5bead056ef2 | **Risk:** high | **Math:** 20

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | FAIL | 2.9s | s\user\AppData\Local\Programs\Python\Python313\Lib\site-packages\_pytest\main.py |
| smoke | FAIL | 24.2s | py:improve_round2: import timed out |
| semgrep | FAIL | 317.3s | semgrep timed out after 300s |
| pip_audit | PASS | 59.1s | pip-audit findings: 0 vulnerabilities across 17 dep(s); scope: requirements file |
| numerical | PASS | 0.2s | 5 values within tolerance |
| numerical_continuity | PASS | 0.0s | numerical continuity: baseline + provenance checks OK |

## Project

- **Path:** C:\Projects\Finrenone
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest tests/test_flagship_playwright_smoke.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-05-05 | CERTIFIED | 5/6 | 90.2s | c9fb5967c8ee6097 |
| 2026-05-05 | REJECT | 5/6 | 172.5s | eb9aa880179cad90 |
| 2026-05-09 | REJECT | 5/6 | 259.4s | e408be710537d004 |
| 2026-05-10 | REJECT | 5/6 | 154.8s | 2075f7ca193c41e2 |
| 2026-05-12 | REJECT | 5/6 | 194.3s | 68c251521869c9d2 |
| 2026-05-13 | REJECT | 5/6 | 233.8s | a7519e093676a2c9 |
| 2026-05-14 | REJECT | 6/6 | 303.1s | ec888ed8e2ff266d |
| 2026-05-15 | REJECT | 6/6 | 366.9s | 614255d08c57d706 |
| 2026-05-16 | REJECT | 6/6 | 636.3s | a03e5920a94e9d22 |
| 2026-05-17 | REJECT | 6/6 | 403.8s | e75ad5bead056ef2 |

## Notes

Witnesses disagree: pip_audit, numerical, numerical_continuity PASS vs test_suite, smoke, semgrep FAIL

**test_suite:** s\user\AppData\Local\Programs\Python\Python313\Lib\site-packages\_pytest\main.py", line 365, in pytest_cmdline_main
    return wrap_session(config, _main)
  File "C:\Users\user\AppData\Local\Programs\

**smoke:** py:improve_round2: import timed out

**semgrep:** semgrep timed out after 300s
