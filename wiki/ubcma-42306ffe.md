# ubcma

**Last verified:** 2026-04-12 02:25 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs numerical FAIL)
**Bundle hash:** 5d7d8dd479a4ec74 | **Risk:** high | **Math:** 11

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 3.6s | .......                                                                  [100%]
 |
| smoke | SKIP | 0.0s | skipped |
| numerical | FAIL | 0.0s | Failed to start: [WinError 2] The system cannot find the file specified |

## Project

- **Path:** C:\ubcma
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest tests/test_smoke.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | FAIL | 1/1 | 300.0s | 1e69d9e49a54861c |
| 2026-04-08 | FAIL | 3/3 | 129.5s | aae6f0747b35b54d |
| 2026-04-08 | REJECT | 3/3 | 31.5s | 207a1e37f614b7e8 |
| 2026-04-09 | REJECT | 2/3 | 11.9s | 380e3a398177acc7 |
| 2026-04-10 | REJECT | 2/3 | 8.0s | 785c1f2797af1d65 |
| 2026-04-11 | REJECT | 2/3 | 6.2s | f04c2ee81d2dd3af |
| 2026-04-12 | REJECT | 2/3 | 3.6s | 5d7d8dd479a4ec74 |

## Notes

Witnesses disagree: test_suite PASS vs numerical FAIL

**numerical:** Failed to start: [WinError 2] The system cannot find the file specified
