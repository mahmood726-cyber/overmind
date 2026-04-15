# four_limb_synthesis

**Last verified:** 2026-04-15 02:13 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs smoke FAIL)
**Bundle hash:** 616a69b51445ca67 | **Risk:** high | **Math:** 2

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 2.5s | ...........                                                              [100%]
 |
| smoke | FAIL | 16.4s | py:io.loaders: Traceback (most recent call last): |

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

## Notes

Witnesses disagree: test_suite PASS vs smoke FAIL

**smoke:** py:io.loaders: Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import io.loaders
ModuleNotFoundError: No module named 'io.loaders'; 'io' is not a package
js:_test_runner.
