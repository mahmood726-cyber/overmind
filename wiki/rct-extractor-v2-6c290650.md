# rct-extractor-v2

**Last verified:** 2026-05-05 16:01 UTC | **Verdict:** FAIL (Hard timeout (3600s) — process tree killed)
**Bundle hash:** 2a9196a885dddcca | **Risk:** high | **Math:** 7

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | FAIL | 3600.0s | Project hung — process tree killed after 3600s |

## Project

- **Path:** C:\Projects\rct-extractor-v2
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest tests/test_ctg_validation.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-15 | FAIL | 1/1 | 0.0s | d3520d4d93497fb1 |
| 2026-04-17 | REJECT | 2/3 | 21.9s | 68a5cf2dd94cf90e |
| 2026-04-19 | REJECT | 2/3 | 22.0s | ad2aa38135d5390b |
| 2026-04-20 | REJECT | 3/4 | 22.4s | 45f0b4da8bcb3d91 |
| 2026-04-25 | REJECT | 3/4 | 26.0s | c2e841eeb71f0041 |
| 2026-04-26 | REJECT | 3/4 | 28.7s | c736d358b53b1250 |
| 2026-04-27 | REJECT | 3/4 | 28.7s | bad6910d688df180 |
| 2026-04-28 | REJECT | 3/4 | 27.8s | 0b9bdcda3383d5ed |
| 2026-05-04 | FAIL | 1/1 | 900.0s | 40b0a3f6612bd6c1 |
| 2026-05-05 | FAIL | 1/1 | 3600.0s | 2a9196a885dddcca |

## Notes

Hard timeout (3600s) — process tree killed

**test_suite:** Project hung — process tree killed after 3600s
