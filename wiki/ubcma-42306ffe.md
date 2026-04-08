# ubcma

**Last verified:** 2026-04-08 22:10 UTC | **Verdict:** FAIL (All witnesses FAIL: test_suite, smoke, numerical)
**Bundle hash:** aae6f0747b35b54d | **Risk:** high | **Math:** 11

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | FAIL | 120.1s | Timed out after 120s |
| smoke | FAIL | 9.4s | examples.quickstart: io\common.py", line 873, in get_handle |
| numerical | FAIL | 0.0s | Blocked: command prefix not allowlisted: C:\Users\user\AppData\Local\Programs\Py |

## Project

- **Path:** C:\ubcma
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | FAIL | 1/1 | 300.0s | 1e69d9e49a54861c |
| 2026-04-08 | FAIL | 3/3 | 129.5s | aae6f0747b35b54d |

## Notes

All witnesses FAIL: test_suite, smoke, numerical

**test_suite:** Timed out after 120s

**smoke:** examples.quickstart: io\common.py", line 873, in get_handle
    handle = open(
        handle,
    ...<3 lines>...
        newline="",
    )
FileNotFoundError: [Errno 2] No such file or directory: 've

**numerical:** Blocked: command prefix not allowlisted: C:\Users\user\AppData\Local\Programs\Python\Python313\python.exe C:\overmind\dat
