# nur-cardiorenal-poc

**Last verified:** 2026-05-14 04:02 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite, semgrep PASS vs smoke FAIL)
**Bundle hash:** 14e2763c1d87c001 | **Risk:** high | **Math:** 7

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 9.6s | .                                                                        [100%]
 |
| smoke | FAIL | 77.0s | py:src.nur_pce.model.hte_bayes: import timed out |
| semgrep | PASS | 37.3s | semgrep findings: ERROR=0 WARNING=0 INFO=0; engine errors=0 |
| pip_audit | SKIP | 0.0s | skipped |

## Project

- **Path:** C:\Projects\nur-cardiorenal-poc
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, javascript, python
- **Test command:** `python -m pytest tests/test_viewer_smoke.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-05-09 | CERTIFIED | 3/4 | 74.1s | f642ca37aabcf7ed |
| 2026-05-10 | CERTIFIED | 3/4 | 56.4s | 729c72af646a2014 |
| 2026-05-12 | CERTIFIED | 3/4 | 67.9s | 3c70f476b1e65e0c |
| 2026-05-13 | CERTIFIED | 3/4 | 75.6s | d53953290b50307e |
| 2026-05-14 | REJECT | 3/4 | 123.9s | 14e2763c1d87c001 |

## Notes

Witnesses disagree: test_suite, semgrep PASS vs smoke FAIL

**smoke:** py:src.nur_pce.model.hte_bayes: import timed out
py:src.nur_pce.pipeline: import timed out
py:src.nur_pce.validate.holdout_runner: import timed out
py:nur_pce.model.hte_bayes: import timed out
py:nur_
