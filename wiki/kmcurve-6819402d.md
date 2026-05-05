# KMcurve

**Last verified:** 2026-05-05 11:24 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite, semgrep, numerical_continuity PASS vs smoke FAIL)
**Bundle hash:** e07b41b8e35ea7c3 | **Risk:** high | **Math:** 20

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 10.2s | ....                                                                     [100%]
 |
| smoke | FAIL | 59.2s | py:analyze_augustus: s,encoding_table)[0] |
| semgrep | PASS | 21.3s | semgrep findings: ERROR=0 WARNING=0 INFO=0; engine errors=0 |
| pip_audit | SKIP | 0.0s | skipped |
| numerical | SKIP | 0.0s | skipped |
| numerical_continuity | PASS | 0.0s | numerical continuity: baseline + provenance checks OK |

## Project

- **Path:** C:\Projects\KMcurve
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, r
- **Test command:** `python -m pytest tests/test_pipeline_smoke.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-17 | REJECT | 2/3 | 66.4s | 851110bc8c6779c1 |
| 2026-04-19 | REJECT | 2/3 | 68.4s | a74f0618548d2349 |
| 2026-04-20 | REJECT | 3/4 | 76.8s | 769f32531e931f7b |
| 2026-04-25 | REJECT | 3/4 | 98.3s | 07b632e18c8ea47f |
| 2026-04-26 | UNVERIFIED | 3/4 | 81.6s | 8eab19f1b0cc001b |
| 2026-04-27 | UNVERIFIED | 3/4 | 99.5s | 46b0c6cf9bfe80a3 |
| 2026-04-28 | UNVERIFIED | 3/4 | 90.6s | bf488203bdb3a9f6 |
| 2026-05-05 | REJECT | 4/6 | 90.7s | e07b41b8e35ea7c3 |

## Notes

Witnesses disagree: test_suite, semgrep, numerical_continuity PASS vs smoke FAIL

**smoke:** py:analyze_augustus: s,encoding_table)[0]
           ~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
UnicodeEncodeError: 'charmap' codec can't encode character '\u2713' in position 0: characte
