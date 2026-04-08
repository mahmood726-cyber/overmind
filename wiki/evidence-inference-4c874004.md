# evidence-inference

**Last verified:** 2026-04-08 20:23 UTC | **Verdict:** FAIL (All witnesses FAIL: test_suite, smoke)
**Bundle hash:** 4e7beda764f8558c | **Risk:** high | **Math:** 18

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | FAIL | 2.2s |  |
| smoke | FAIL | 10.2s | verify_span_quality: ntences, gen_exact_evid_array |
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

## Notes

All witnesses FAIL: test_suite, smoke

**smoke:** verify_span_quality: ntences, gen_exact_evid_array
  File "C:\Projects\evidence-inference\evidence_inference\preprocess\sentence_split.py", line 8, in <module>
    import spacy
ModuleNotFoundError: No
