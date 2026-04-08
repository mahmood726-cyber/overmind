# ipd-meta-pro-link

**Last verified:** 2026-04-08 22:10 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs smoke FAIL)
**Bundle hash:** 0088cb59051b088b | **Risk:** high | **Math:** 20

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 17.1s | ======================================================================
IPD Meta- |
| smoke | FAIL | 0.2s | dev.dedup_functions: This script is retired. dev/modules/ is the authoritative s |
| numerical | SKIP | 0.0s | skipped |

## Project

- **Path:** C:\Projects\ipd-meta-pro-link
- **Type:** browser_app
- **Stack:** css, html, javascript
- **Test command:** `python dev/build-scripts/user_flow_smoke_test.py`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | REJECT | 2/3 | 31.4s | 2380026aaea581e6 |
| 2026-04-08 | REJECT | 2/3 | 17.3s | 0088cb59051b088b |

## Notes

Witnesses disagree: test_suite PASS vs smoke FAIL

**smoke:** dev.dedup_functions: This script is retired. dev/modules/ is the authoritative source. Edit the relevant module and run `python dev/build.py build` instead of mutating ipd-meta-pro.html directly.
