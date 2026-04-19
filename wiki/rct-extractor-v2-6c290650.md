# rct-extractor-v2

**Last verified:** 2026-04-19 02:36 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs smoke FAIL)
**Bundle hash:** ad2aa38135d5390b | **Risk:** high | **Math:** 15

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 4.2s | est_ctg_validation.py::TestCTGValidator::test_values_match_zero PASSED [ 13%]
te |
| smoke | FAIL | 17.8s | py:gold_data.mega.v10_pdf_results.extract_batch_052:   File "C:\Projects\rct-ext |
| numerical | SKIP | 0.0s | skipped |

## Project

- **Path:** C:\Projects\rct-extractor-v2
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest tests/test_ctg_validation.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | PASS | 2/3 | 11.2s | 22708e19c3947096 |
| 2026-04-08 | PASS | 2/3 | 18.6s | 0d36ad1cebc18b18 |
| 2026-04-09 | PASS | 2/3 | 17.6s | a07fb82e3d85f341 |
| 2026-04-10 | PASS | 2/3 | 40.8s | ba7416ffef8e7129 |
| 2026-04-11 | PASS | 2/3 | 8.1s | 1c670d3294f559b2 |
| 2026-04-12 | PASS | 2/3 | 12.8s | 3a4c7f8776a98cf5 |
| 2026-04-13 | PASS | 2/3 | 7.3s | 2e65c96b562ffffb |
| 2026-04-15 | FAIL | 1/1 | 0.0s | d3520d4d93497fb1 |
| 2026-04-17 | REJECT | 2/3 | 21.9s | 68a5cf2dd94cf90e |
| 2026-04-19 | REJECT | 2/3 | 22.0s | ad2aa38135d5390b |

## Notes

Witnesses disagree: test_suite PASS vs smoke FAIL

**smoke:** py:gold_data.mega.v10_pdf_results.extract_batch_052:   File "C:\Projects\rct-extractor-v2\gold_data\mega\v10_pdf_results\extract_batch_052.py", line 7, in <module>
    pdf_path = sys.argv[1]
         
