# metasprint-autopilot

**Last verified:** 2026-05-04 20:36 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite, semgrep, pip_audit, numerical, numerical_continuity PASS vs smoke FAIL)
**Bundle hash:** aae6752fc1186f1f | **Risk:** high | **Math:** 13

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 11.8s | ..                                                                       [100%]
 |
| smoke | FAIL | 9.2s | py:validation.selenium_12_user_advanced_journal_review: autopilot\validation\sel |
| semgrep | PASS | 40.6s | semgrep findings: ERROR=0 WARNING=3 INFO=0; engine errors=4
3 advisory WARNING f |
| pip_audit | PASS | 45.4s | pip-audit findings: 0 vulnerabilities across 24 dep(s); scope: requirements file |
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

## Notes

Witnesses disagree: test_suite, semgrep, pip_audit, numerical, numerical_continuity PASS vs smoke FAIL

**smoke:** py:validation.selenium_12_user_advanced_journal_review: autopilot\validation\selenium_12_user_advanced_journal_review.py", line 22, in <module>
    from browser_runtime import ensure_local_browser_lib
