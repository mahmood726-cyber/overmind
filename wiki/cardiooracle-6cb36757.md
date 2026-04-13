# CardioOracle

**Last verified:** 2026-04-13 02:18 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs smoke FAIL)
**Bundle hash:** 38c2c460dce9fd7d | **Risk:** high | **Math:** 20

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 8.1s | ..............................                                           [100%]
 |
| smoke | FAIL | 17.1s | debug_test: Verifier [0x2eee9a+2baa] |
| numerical | SKIP | 0.0s | skipped |

## Project

- **Path:** C:\Models\CardioOracle
- **Type:** browser_app
- **Stack:** css, html, javascript
- **Test command:** `python -m pytest tests/test_curation.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | FAIL | 1/1 | 300.0s | ec4b2ac9d0d4cecc |
| 2026-04-08 | FAIL | 1/1 | 300.0s | 2322da815c19e7a0 |
| 2026-04-08 | FAIL | 1/1 | 300.0s | fa8c05ade29db7b1 |
| 2026-04-09 | FAIL | 1/1 | 300.0s | 4d06987293db7f8a |
| 2026-04-10 | FAIL | 1/1 | 300.0s | 9fa9840d991498d2 |
| 2026-04-11 | FAIL | 1/1 | 300.0s | 86e3651b3b90bf0f |
| 2026-04-12 | FAIL | 1/1 | 300.0s | bb641ab77c157aba |
| 2026-04-13 | REJECT | 2/3 | 25.2s | 38c2c460dce9fd7d |

## Notes

Witnesses disagree: test_suite PASS vs smoke FAIL

**smoke:** debug_test: Verifier [0x2eee9a+2baa]
	KERNEL32!BaseThreadInitThunk [0x75d85d49+19]
	ntdll!RtlInitializeExceptionChain [0x770dd83b+6b]
	ntdll!RtlGetAppContainerNamedObjectPath [0x770dd7c1+231]
	(No sym
