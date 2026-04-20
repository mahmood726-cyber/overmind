# rct-extractor-v2

**Last verified:** 2026-04-20 02:42 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite, numerical_continuity PASS vs smoke FAIL)
**Bundle hash:** 45f0b4da8bcb3d91 | **Risk:** high | **Math:** 15

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 5.4s | /test_ctg_validation.py::TestIntegration::test_validate_study_no_effects PASSED  |
| smoke | FAIL | 17.1s | py:gold_data.mega.v10_batches.extract_009_final: tf-8') as f: |
| numerical | SKIP | 0.0s | skipped |
| numerical_continuity | PASS | 0.0s | numerical continuity: baseline + provenance checks OK |

## Project

- **Path:** C:\Projects\rct-extractor-v2
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest tests/test_ctg_validation.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | PASS | 2/3 | 18.6s | 0d36ad1cebc18b18 |
| 2026-04-09 | PASS | 2/3 | 17.6s | a07fb82e3d85f341 |
| 2026-04-10 | PASS | 2/3 | 40.8s | ba7416ffef8e7129 |
| 2026-04-11 | PASS | 2/3 | 8.1s | 1c670d3294f559b2 |
| 2026-04-12 | PASS | 2/3 | 12.8s | 3a4c7f8776a98cf5 |
| 2026-04-13 | PASS | 2/3 | 7.3s | 2e65c96b562ffffb |
| 2026-04-15 | FAIL | 1/1 | 0.0s | d3520d4d93497fb1 |
| 2026-04-17 | REJECT | 2/3 | 21.9s | 68a5cf2dd94cf90e |
| 2026-04-19 | REJECT | 2/3 | 22.0s | ad2aa38135d5390b |
| 2026-04-20 | REJECT | 3/4 | 22.4s | 45f0b4da8bcb3d91 |

## Notes

Witnesses disagree: test_suite, numerical_continuity PASS vs smoke FAIL

**smoke:** py:gold_data.mega.v10_batches.extract_009_final: tf-8') as f:
         ~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\user\\rct-extractor-v
