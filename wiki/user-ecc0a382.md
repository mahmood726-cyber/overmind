# user

**Last verified:** 2026-04-25 02:49 UTC | **Verdict:** FAIL (Hard timeout (300s) — process killed)
**Bundle hash:** dfd4a7a667a7089c | **Risk:** high | **Math:** 14

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | FAIL | 300.0s | Project hung — killed after 300s |

## Project

- **Path:** C:\Users\user
- **Type:** browser_app
- **Stack:** css, html, javascript
- **Test command:** `python -m pytest tests/test_integrity.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-17 | FAIL | 1/1 | 300.0s | 1055f3b1a5c66332 |
| 2026-04-19 | REJECT | 2/3 | 10.9s | 659993633edf0a0f |
| 2026-04-20 | FAIL | 1/1 | 300.0s | f3270bff602be8b8 |
| 2026-04-25 | FAIL | 1/1 | 300.0s | dfd4a7a667a7089c |

## Notes

Hard timeout (300s) — process killed

**test_suite:** Project hung — killed after 300s
