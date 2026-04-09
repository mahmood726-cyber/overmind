# GRMA_paper

**Last verified:** 2026-04-09 01:34 UTC | **Verdict:** FAIL (All witnesses FAIL: test_suite, smoke)
**Bundle hash:** 8675f8cbd45ef4d6 | **Risk:** high | **Math:** 7

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | FAIL | 0.0s | Failed to start: [WinError 2] The system cannot find the file specified |
| smoke | FAIL | 10.8s | dev_analyze_rmse_coverage:  encoding='utf-8') as f: |

## Project

- **Path:** C:\Users\user\OneDrive\Backups\Models\GRMA_paper
- **Type:** python_tool
- **Stack:** python
- **Test command:** `Rscript test_edge_cases.R`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-09 | FAIL | 2/2 | 10.8s | 8675f8cbd45ef4d6 |

## Notes

All witnesses FAIL: test_suite, smoke

**test_suite:** Failed to start: [WinError 2] The system cannot find the file specified

**smoke:** dev_analyze_rmse_coverage:  encoding='utf-8') as f:
         ~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\user\\Downloads\\GRMA_pap
