# FATIHA_Project

**Last verified:** 2026-05-04 21:18 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite, semgrep, numerical_continuity PASS vs numerical FAIL)
**Bundle hash:** ff48c408979bf0fc | **Risk:** high | **Math:** 11

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 2.9s | s...                                                                     [100%]
 |
| smoke | SKIP | 0.0s | skipped |
| semgrep | PASS | 21.1s | semgrep findings: ERROR=0 WARNING=0 INFO=0; engine errors=0 |
| pip_audit | SKIP | 0.0s | skipped |
| numerical | FAIL | 3.7s | Could not parse output as JSON |
| numerical_continuity | PASS | 0.0s | numerical continuity: baseline + provenance checks OK |

## Project

- **Path:** C:\Models\FATIHA_Project
- **Type:** r_project
- **Stack:** r
- **Test command:** `python -m pytest tests/test_smoke.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-11 | FAIL | 1/3 | 0.0s | b819336353b681b5 |
| 2026-04-12 | FAIL | 1/3 | 0.0s | b20af1445ed18b1d |
| 2026-04-13 | FAIL | 1/3 | 0.0s | f24961bd5cd5b450 |
| 2026-04-15 | FAIL | 1/1 | 0.0s | 474b86263293cb80 |
| 2026-04-17 | FAIL | 1/3 | 3.8s | d8fe252e0640ddfb |
| 2026-04-19 | FAIL | 1/3 | 3.6s | f7cac7a14aa14267 |
| 2026-04-20 | REJECT | 2/4 | 3.6s | cd7a901aad66e94f |
| 2026-04-25 | REJECT | 2/4 | 4.7s | ba9f0dade0e2f62f |
| 2026-05-04 | UNVERIFIED | 3/6 | 24.9s | 4e3a976e1aaee9ce |
| 2026-05-04 | REJECT | 4/6 | 27.7s | ff48c408979bf0fc |

## Notes

Witnesses disagree: test_suite, semgrep, numerical_continuity PASS vs numerical FAIL

**numerical:** Could not parse output as JSON
