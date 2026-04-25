# KMcurve

**Last verified:** 2026-04-25 02:49 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite, numerical_continuity PASS vs smoke FAIL)
**Bundle hash:** 07b632e18c8ea47f | **Risk:** high | **Math:** 20

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 17.9s | ....                                                                     [100%]
 |
| smoke | FAIL | 80.4s | py:extract_and_validate_curves: rves.py", line 22, in <module> |
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

## Notes

Witnesses disagree: test_suite, numerical_continuity PASS vs smoke FAIL

**smoke:** py:extract_and_validate_curves: rves.py", line 22, in <module>
    from batch_processor import process_pdf
ImportError: cannot import name 'process_pdf' from 'batch_processor' (C:\Projects\KMcurve\ipd
