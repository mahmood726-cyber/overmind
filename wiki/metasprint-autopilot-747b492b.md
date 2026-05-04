# metasprint-autopilot

**Last verified:** 2026-05-04 20:27 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite, semgrep, pip_audit, numerical, numerical_continuity PASS vs smoke FAIL)
**Bundle hash:** 1c5d8227bc5191bf | **Risk:** high | **Math:** 13

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 12.5s | ..                                                                       [100%]
 |
| smoke | FAIL | 13.3s | py:truthcert1_work.update_forest_plot: : |
| semgrep | PASS | 44.9s | semgrep findings: ERROR=0 WARNING=3 INFO=0; engine errors=8
3 advisory WARNING f |
| pip_audit | PASS | 56.9s | pip-audit findings: 0 vulnerabilities across 24 dep(s); scope: requirements file |
| numerical | PASS | 0.1s | 7 values within tolerance |
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

## Notes

Witnesses disagree: test_suite, semgrep, pip_audit, numerical, numerical_continuity PASS vs smoke FAIL

**smoke:** py:truthcert1_work.update_forest_plot: :
         ~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Truthcer
