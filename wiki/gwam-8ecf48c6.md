# GWAM

**Last verified:** 2026-04-08 23:40 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs smoke FAIL)
**Bundle hash:** c1535062fa90d6d7 | **Risk:** high | **Math:** 7

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 12.5s | ...........                                                              [100%]
 |
| smoke | FAIL | 15.8s | scripts.build_pairwise70_ctgov_linkage_summary: els\GWAM\scripts\build_pairwise7 |

## Project

- **Path:** C:\Models\GWAM
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest tests/test_bayesian_gwam.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | REJECT | 2/2 | 27.7s | 81911582fd753f3b |
| 2026-04-08 | REJECT | 2/2 | 20.1s | 86df07cd9f4b1cdf |
| 2026-04-08 | REJECT | 2/2 | 28.2s | c1535062fa90d6d7 |

## Notes

Witnesses disagree: test_suite PASS vs smoke FAIL

**smoke:** scripts.build_pairwise70_ctgov_linkage_summary: els\GWAM\scripts\build_pairwise70_ctgov_linkage_summary.py", line 34, in <module>
    from gwam_utils import parse_bool, safe_float, sanitize_csv_cell
M
