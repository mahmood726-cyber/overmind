# four_limb_synthesis

**Last verified:** 2026-04-27 02:43 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs smoke FAIL)
**Bundle hash:** b32dca3099a1c91f | **Risk:** high | **Math:** 2

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 6.1s | ...........                                                              [100%]
 |
| smoke | FAIL | 29.4s | py:io.loaders: Traceback (most recent call last): |

## Project

- **Path:** C:\Projects\four_limb_synthesis
- **Type:** browser_app
- **Stack:** css, html, javascript
- **Test command:** `python -m pytest tests/test_core.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-10 | CERTIFIED | 2/2 | 16.2s | 418bf9505a8673b3 |
| 2026-04-11 | CERTIFIED | 2/2 | 16.2s | ffc36fedd27bd68c |
| 2026-04-12 | CERTIFIED | 2/2 | 11.4s | dff202b64ac3b783 |
| 2026-04-13 | CERTIFIED | 2/2 | 11.3s | 5c318522845c260a |
| 2026-04-15 | REJECT | 2/2 | 18.9s | 616a69b51445ca67 |
| 2026-04-26 | REJECT | 2/2 | 31.7s | 9dddeaee666dfa3a |
| 2026-04-27 | REJECT | 2/2 | 35.5s | b32dca3099a1c91f |

## Notes

Witnesses disagree: test_suite PASS vs smoke FAIL

**smoke:** py:io.loaders: Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import io.loaders
ModuleNotFoundError: No module named 'io.loaders'; 'io' is not a package
js:_test_runner.
