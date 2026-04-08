# ubcma

**Last verified:** 2026-04-08 23:40 UTC | **Verdict:** REJECT (Witnesses disagree: test_suite PASS vs smoke, numerical FAIL)
**Bundle hash:** 207a1e37f614b7e8 | **Risk:** high | **Math:** 11

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| test_suite | PASS | 16.8s | .......                                                                  [100%]
 |
| smoke | FAIL | 14.7s | examples.quickstart: io\common.py", line 873, in get_handle |
| numerical | FAIL | 0.0s | Failed to start: [WinError 2] The system cannot find the file specified |

## Project

- **Path:** C:\ubcma
- **Type:** hybrid_browser_analytics_app
- **Stack:** css, html, javascript, python
- **Test command:** `python -m pytest tests/test_smoke.py -q`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| 2026-04-08 | FAIL | 1/1 | 300.0s | 1e69d9e49a54861c |
| 2026-04-08 | FAIL | 3/3 | 129.5s | aae6f0747b35b54d |
| 2026-04-08 | REJECT | 3/3 | 31.5s | 207a1e37f614b7e8 |

## Notes

Witnesses disagree: test_suite PASS vs smoke, numerical FAIL

**smoke:** examples.quickstart: io\common.py", line 873, in get_handle
    handle = open(
        handle,
    ...<3 lines>...
        newline="",
    )
FileNotFoundError: [Errno 2] No such file or directory: 've

**numerical:** Failed to start: [WinError 2] The system cannot find the file specified
