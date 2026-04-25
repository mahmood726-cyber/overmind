# FATIHA_Project

**Last verified:** 2026-04-25 02:49 UTC | **Verdict:** REJECT (Witnesses disagree: numerical_continuity PASS vs test_suite FAIL)
**Bundle hash:** ba9f0dade0e2f62f | **Risk:** high | **Math:** 11

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | FAIL | 4.7s | Error in h(simpleError(msg, call)) : failed to install: |
| smoke | SKIP | 0.0s | skipped |
| numerical | SKIP | 0.0s | skipped |
| numerical_continuity | PASS | 0.0s | numerical continuity: baseline + provenance checks OK |

## Project

- **Path:** C:\Models\FATIHA_Project
- **Type:** r_project
- **Stack:** r
- **Test command:** `Rscript -e "devtools::test()"`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | FAIL | 1/3 | 0.0s | d529cd4e021f2fb8 |
| 2026-04-10 | FAIL | 1/3 | 0.0s | c876529edc95060a |
| 2026-04-11 | FAIL | 1/3 | 0.0s | b819336353b681b5 |
| 2026-04-12 | FAIL | 1/3 | 0.0s | b20af1445ed18b1d |
| 2026-04-13 | FAIL | 1/3 | 0.0s | f24961bd5cd5b450 |
| 2026-04-15 | FAIL | 1/1 | 0.0s | 474b86263293cb80 |
| 2026-04-17 | FAIL | 1/3 | 3.8s | d8fe252e0640ddfb |
| 2026-04-19 | FAIL | 1/3 | 3.6s | f7cac7a14aa14267 |
| 2026-04-20 | REJECT | 2/4 | 3.6s | cd7a901aad66e94f |
| 2026-04-25 | REJECT | 2/4 | 4.7s | ba9f0dade0e2f62f |

## Notes

Witnesses disagree: numerical_continuity PASS vs test_suite FAIL

**test_suite:** Error in h(simpleError(msg, call)) : failed to install:
installation of renv failed
===========================
ERROR: failed to lock directory 'C:/Users/user/AppData/Local/R/cache/R/renv/library/FATI
