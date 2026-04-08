# GRMA_paper

**Last verified:** 2026-04-08 23:40 UTC | **Verdict:** FAIL (All witnesses FAIL: test_suite, smoke)
**Bundle hash:** 1b9927272c6f0f55 | **Risk:** high | **Math:** 7

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | FAIL | 0.0s | Failed to start: [WinError 2] The system cannot find the file specified |
| smoke | FAIL | 16.4s | dev_analyze_rmse_coverage:  encoding='utf-8') as f: |

## Project

- **Path:** C:\Models\GRMA_paper
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `Rscript test_edge_cases.R`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | FAIL | 2/2 | 10.4s | 68b1f5a39c2da2c6 |
| 2026-04-08 | FAIL | 2/2 | 8.6s | 615daeccf5afddd3 |
| 2026-04-08 | FAIL | 2/2 | 16.4s | 1b9927272c6f0f55 |

## Notes

All witnesses FAIL: test_suite, smoke

**test_suite:** Failed to start: [WinError 2] The system cannot find the file specified

**smoke:** dev_analyze_rmse_coverage:  encoding='utf-8') as f:
         ~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\user\\Downloads\\GRMA_pap
