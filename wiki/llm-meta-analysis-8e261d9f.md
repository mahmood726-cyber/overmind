# llm-meta-analysis

**Last verified:** 2026-05-05 11:11 UTC | **Verdict:** CERTIFIED (5/5 witnesses agree PASS)
**Bundle hash:** cc1f8139da662fdc | **Risk:** high | **Math:** 10

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 2.5s | .                                                                        [100%]
 |
| smoke | PASS | 89.4s | 40 modules imported OK |
| semgrep | PASS | 40.3s | semgrep findings: ERROR=0 WARNING=91 INFO=0; engine errors=0
91 advisory WARNING |
| pip_audit | SKIP | 0.0s | skipped |
| numerical | PASS | 2.3s | 10 values within tolerance |
| numerical_continuity | PASS | 0.0s | numerical continuity: baseline + provenance checks OK |

## Project

- **Path:** C:\Projects\llm-meta-analysis
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest tests/test_smoke.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-15 | FAIL | 1/1 | 0.0s | 349cc2bc901925b2 |
| 2026-04-17 | UNVERIFIED | 2/3 | 62.1s | 0c5a762b767502ed |
| 2026-04-19 | REJECT | 2/3 | 63.0s | 09e384e9a30eb462 |
| 2026-04-20 | UNVERIFIED | 3/4 | 62.9s | 8915919da5185f92 |
| 2026-04-25 | REJECT | 3/4 | 80.9s | 90729ffbfefd048a |
| 2026-04-26 | UNVERIFIED | 3/4 | 76.4s | 80daa6f592e558f9 |
| 2026-04-27 | UNVERIFIED | 3/4 | 83.6s | 17f65fd289d9335f |
| 2026-04-28 | UNVERIFIED | 3/4 | 82.5s | 12ff4c594b5b9761 |
| 2026-05-04 | UNVERIFIED | 4/6 | 112.5s | fbbf9ebe200e4253 |
| 2026-05-05 | CERTIFIED | 5/6 | 134.5s | cc1f8139da662fdc |
