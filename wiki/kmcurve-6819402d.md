# KMcurve

**Last verified:** 2026-04-17 02:44 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs smoke FAIL)
**Bundle hash:** 851110bc8c6779c1 | **Risk:** high | **Math:** 20

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 10.3s | ....                                                                     [100%]
 |
| smoke | FAIL | 56.0s | py:extract_and_validate_curves: rves.py", line 22, in <module> |
| numerical | SKIP | 0.0s | skipped |

## Project

- **Path:** C:\Projects\KMcurve
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, r
- **Test command:** `python -m pytest tests/test_pipeline_smoke.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-17 | REJECT | 2/3 | 66.4s | 851110bc8c6779c1 |

## Notes

Witnesses disagree: test_suite PASS vs smoke FAIL

**smoke:** py:extract_and_validate_curves: rves.py", line 22, in <module>
    from batch_processor import process_pdf
ImportError: cannot import name 'process_pdf' from 'batch_processor' (C:\Projects\KMcurve\ipd
