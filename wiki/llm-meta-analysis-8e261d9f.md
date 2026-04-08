# llm-meta-analysis

**Last verified:** 2026-04-08 23:40 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs smoke FAIL)
**Bundle hash:** ac6436754303bc28 | **Risk:** high | **Math:** 10

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 8.7s | .                                                                        [100%]
 |
| smoke | FAIL | 120.6s | evaluation.bayesian_meta_analysis: n_meta_analysis |
| numerical | SKIP | 0.0s | skipped |

## Project

- **Path:** C:\Projects\llm-meta-analysis
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest tests/test_smoke.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | REJECT | 2/3 | 80.7s | 00e476430dfd8592 |
| 2026-04-08 | REJECT | 2/3 | 103.7s | 03567b0635662d3c |
| 2026-04-08 | REJECT | 2/3 | 129.3s | ac6436754303bc28 |

## Notes

Witnesses disagree: test_suite PASS vs smoke FAIL

**smoke:** evaluation.bayesian_meta_analysis: n_meta_analysis
  File "C:\Projects\llm-meta-analysis\evaluation\bayesian_meta_analysis.py", line 324
    lors = []
             ^
IndentationError: unindent does no
