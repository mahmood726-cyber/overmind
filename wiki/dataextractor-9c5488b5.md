# Dataextractor

**Last verified:** 2026-04-27 02:43 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite, numerical_continuity PASS vs smoke FAIL)
**Bundle hash:** 7781355d4e5c3fed | **Risk:** high | **Math:** 18

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 2.1s | 
  ✓ R code includes rma()
  ✓ R code includes forest()
  ✓ R code includes funn |
| smoke | FAIL | 17.3s | py:expand_validation: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ |
| numerical | SKIP | 0.0s | skipped |
| numerical_continuity | PASS | 0.0s | numerical continuity: baseline + provenance checks OK |

## Project

- **Path:** C:\Projects\Dataextractor
- **Type:** browser_app
- **Stack:** css, html, javascript
- **Test command:** `npm run test`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-11 | FAIL | 1/1 | 300.0s | dd8f7aab6f57f167 |
| 2026-04-12 | FAIL | 2/3 | 34.6s | 91418e1d77c44552 |
| 2026-04-13 | FAIL | 2/3 | 24.1s | f7b5c77bc491a363 |
| 2026-04-15 | FAIL | 1/1 | 0.0s | 44121cac422e4788 |
| 2026-04-17 | FAIL | 2/3 | 18.1s | 3df2500392caa5d9 |
| 2026-04-19 | FAIL | 2/3 | 17.2s | 274b93cfd8b27691 |
| 2026-04-20 | REJECT | 3/4 | 16.4s | 34f97199caa73b1e |
| 2026-04-25 | REJECT | 3/4 | 20.8s | 7ce2c192d60211e9 |
| 2026-04-26 | REJECT | 3/4 | 17.2s | 9c77ec239663c384 |
| 2026-04-27 | REJECT | 3/4 | 19.4s | 7781355d4e5c3fed |

## Notes

Witnesses disagree: test_suite, numerical_continuity PASS vs smoke FAIL

**smoke:** py:expand_validation: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\user\\Downloads\\Dataextractor\\vali
