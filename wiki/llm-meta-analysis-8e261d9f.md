# llm-meta-analysis

**Last verified:** 2026-04-20 02:42 UTC | **Verdict:** UNVERIFIED (3/3 witnesses PASS but numerical witness SKIPPED (baseline missing) — NOT a release pass (upgraded after retry))
**Bundle hash:** 8915919da5185f92 | **Risk:** high | **Math:** 10

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 1.8s | .                                                                        [100%]
 |
| smoke | PASS | 61.1s | 40 modules imported OK |
| numerical | SKIP | 0.0s | skipped |
| numerical_continuity | PASS | 0.0s | numerical continuity: baseline + provenance checks OK |

## Project

- **Path:** C:\Projects\llm-meta-analysis
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest tests/test_smoke.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | REJECT | 2/3 | 129.3s | ac6436754303bc28 |
| 2026-04-09 | REJECT | 2/3 | 61.8s | 63d0abb9660d11c5 |
| 2026-04-10 | REJECT | 2/3 | 66.9s | 7095d58901b6e158 |
| 2026-04-11 | REJECT | 2/3 | 37.4s | 256e52d8246a772d |
| 2026-04-12 | REJECT | 2/3 | 34.5s | 77d10392a1fa5199 |
| 2026-04-13 | REJECT | 2/3 | 30.0s | d43d57fdfd85436d |
| 2026-04-15 | FAIL | 1/1 | 0.0s | 349cc2bc901925b2 |
| 2026-04-17 | UNVERIFIED | 2/3 | 62.1s | 0c5a762b767502ed |
| 2026-04-19 | REJECT | 2/3 | 63.0s | 09e384e9a30eb462 |
| 2026-04-20 | UNVERIFIED | 3/4 | 62.9s | 8915919da5185f92 |
