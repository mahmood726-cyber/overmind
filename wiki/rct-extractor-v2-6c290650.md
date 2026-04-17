# rct-extractor-v2

**Last verified:** 2026-04-17 02:44 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs smoke FAIL)
**Bundle hash:** 68a5cf2dd94cf90e | **Risk:** high | **Math:** 15

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 4.4s | dation.py::TestCTGScraper::test_scraper_has_fetch_multiple_method PASSED [ 13%]
 |
| smoke | FAIL | 17.5s | py:gold_data.mega.v10_batches.extract_009_final: tf-8') as f: |
| numerical | SKIP | 0.0s | skipped |

## Project

- **Path:** C:\Projects\rct-extractor-v2
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest tests/test_ctg_validation.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | PASS | 2/3 | 17.5s | 60929a85f8603698 |
| 2026-04-08 | PASS | 2/3 | 11.2s | 22708e19c3947096 |
| 2026-04-08 | PASS | 2/3 | 18.6s | 0d36ad1cebc18b18 |
| 2026-04-09 | PASS | 2/3 | 17.6s | a07fb82e3d85f341 |
| 2026-04-10 | PASS | 2/3 | 40.8s | ba7416ffef8e7129 |
| 2026-04-11 | PASS | 2/3 | 8.1s | 1c670d3294f559b2 |
| 2026-04-12 | PASS | 2/3 | 12.8s | 3a4c7f8776a98cf5 |
| 2026-04-13 | PASS | 2/3 | 7.3s | 2e65c96b562ffffb |
| 2026-04-15 | FAIL | 1/1 | 0.0s | d3520d4d93497fb1 |
| 2026-04-17 | REJECT | 2/3 | 21.9s | 68a5cf2dd94cf90e |

## Notes

Witnesses disagree: test_suite PASS vs smoke FAIL

**smoke:** py:gold_data.mega.v10_batches.extract_009_final: tf-8') as f:
         ~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\user\\rct-extractor-v
