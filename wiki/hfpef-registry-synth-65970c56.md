# hfpef_registry_synth

**Last verified:** 2026-05-05 10:02 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite, smoke, semgrep, numerical_continuity PASS vs numerical FAIL)
**Bundle hash:** 4965944054a31eed | **Risk:** high | **Math:** 14

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 4.8s | .                                                                        [100%]
 |
| smoke | PASS | 30.3s | 40 modules imported OK |
| semgrep | PASS | 133.8s | semgrep findings: ERROR=0 WARNING=0 INFO=0; engine errors=0 |
| pip_audit | SKIP | 0.0s | skipped |
| numerical | FAIL | 0.2s | Numerical drift: safe_float_bad: missing in output |
| numerical_continuity | PASS | 0.0s | numerical continuity: baseline + provenance checks OK |

## Project

- **Path:** C:\Projects\hfpef_registry_synth
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python, r
- **Test command:** `python -m pytest tests/test_smoke_pipeline.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-15 | FAIL | 1/1 | 0.0s | 5c6316dfe9f2d27a |
| 2026-04-17 | UNVERIFIED | 2/3 | 30.1s | 8062423f0caf8d34 |
| 2026-04-19 | UNVERIFIED | 2/3 | 28.6s | 2add3201209f7001 |
| 2026-04-20 | UNVERIFIED | 3/4 | 29.7s | 4f973a17a70d6dc0 |
| 2026-04-25 | UNVERIFIED | 3/4 | 38.8s | 96d8dd29fb796c6f |
| 2026-04-26 | UNVERIFIED | 3/4 | 40.6s | 995d869603c70686 |
| 2026-04-27 | UNVERIFIED | 3/4 | 44.9s | d198f506da75b72c |
| 2026-04-28 | UNVERIFIED | 3/4 | 76.6s | 166c9c2f38eede25 |
| 2026-05-04 | UNVERIFIED | 4/6 | 158.6s | 5b6315546986883f |
| 2026-05-05 | REJECT | 5/6 | 169.1s | 4965944054a31eed |

## Notes

Witnesses disagree: test_suite, smoke, semgrep, numerical_continuity PASS vs numerical FAIL

**numerical:** Numerical drift: safe_float_bad: missing in output
