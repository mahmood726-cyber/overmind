# prognostic-meta

**Last verified:** 2026-04-12 02:25 UTC | **Verdict:** FAIL (Single witness: test_suite FAIL)
**Bundle hash:** 0388052fe50cef63 | **Risk:** high | **Math:** 20

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | FAIL | 0.0s | Failed to start: [WinError 267] The directory name is invalid |
| smoke | SKIP | 0.0s | skipped |
| numerical | SKIP | 0.0s | skipped |

## Project

- **Path:** C:\Projects\prognostic-meta
- **Type:** browser_app
- **Stack:** css, html, javascript
- **Test command:** `python -m pytest tests/test_smoke.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | PASS | 1/3 | 3.0s | 4812ce1415856e8a |
| 2026-04-08 | PASS | 1/3 | 1.9s | e61f9f12bd4d7ce5 |
| 2026-04-08 | PASS | 1/3 | 3.6s | 5b4ecab7564716a8 |
| 2026-04-09 | PASS | 1/3 | 6.2s | 3a530d79f690f726 |
| 2026-04-10 | FAIL | 1/3 | 0.0s | 85c0bfdbf286b3b0 |
| 2026-04-11 | FAIL | 1/3 | 0.0s | b906e05a5755fab5 |
| 2026-04-12 | FAIL | 1/3 | 0.0s | 0388052fe50cef63 |

## Notes

Single witness: test_suite FAIL

**test_suite:** Failed to start: [WinError 267] The directory name is invalid
