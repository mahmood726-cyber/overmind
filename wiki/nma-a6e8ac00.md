# NMA

**Last verified:** 2026-05-04 21:08 UTC | **Verdict:** CERTIFIED (4/4 witnesses agree PASS)
**Bundle hash:** 02f11aebde791dfe | **Risk:** high | **Math:** 11

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 1.6s | ✔ | F W  S  OK | Context

⠏ |          0 | basic                                 |
| smoke | SKIP | 0.0s | skipped |
| semgrep | PASS | 16.5s | semgrep findings: ERROR=0 WARNING=0 INFO=0; engine errors=0 |
| pip_audit | SKIP | 0.0s | skipped |
| numerical | PASS | 1.1s | 9 values within tolerance |
| numerical_continuity | PASS | 0.0s | numerical continuity: baseline + provenance checks OK |

## Project

- **Path:** C:\Projects\NMA
- **Type:** r_project
- **Stack:** r
- **Test command:** `Rscript -e "testthat::test_dir('tests/testthat')"`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-19 | PASS | 1/3 | 2.2s | a69ee28bff1931ed |
| 2026-04-20 | UNVERIFIED | 2/4 | 2.7s | 7986b1041c2c12fb |
| 2026-04-25 | UNVERIFIED | 2/4 | 2.9s | 570590b8f743996c |
| 2026-04-26 | UNVERIFIED | 2/4 | 3.1s | b33e232a3b020732 |
| 2026-04-27 | UNVERIFIED | 2/4 | 3.4s | 62ddf778cbbd6cd3 |
| 2026-04-28 | UNVERIFIED | 2/4 | 3.7s | 081ea717c7a89b40 |
| 2026-05-04 | REJECT | 3/6 | 14.1s | b5219d0cb3b05b2b |
| 2026-05-04 | UNVERIFIED | 3/6 | 13.3s | 633d9bb94a86de54 |
| 2026-05-04 | UNVERIFIED | 3/6 | 27.4s | 0cfc4a3b0e12469b |
| 2026-05-04 | CERTIFIED | 4/6 | 19.1s | 02f11aebde791dfe |
