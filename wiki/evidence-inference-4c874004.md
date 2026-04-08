# evidence-inference

**Last verified:** 2026-04-08 23:40 UTC | **Verdict:** FAIL (All witnesses FAIL: test_suite, smoke)
**Bundle hash:** 0d18f60c7a92924d | **Risk:** high | **Math:** 18

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | FAIL | 1.3s |  |
| smoke | FAIL | 12.7s | verify_span_quality: ntences, gen_exact_evid_array |
| numerical | SKIP | 0.0s | skipped |

## Project

- **Path:** C:\Projects\evidence-inference
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest tests/test_imports.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | FAIL | 2/3 | 12.5s | 4e7beda764f8558c |
| 2026-04-08 | FAIL | 2/3 | 10.7s | 800114a4296a10e3 |
| 2026-04-08 | FAIL | 2/3 | 13.9s | 0d18f60c7a92924d |

## Notes

All witnesses FAIL: test_suite, smoke

**smoke:** verify_span_quality: ntences, gen_exact_evid_array
  File "C:\Projects\evidence-inference\evidence_inference\preprocess\sentence_split.py", line 8, in <module>
    import spacy
ModuleNotFoundError: No
