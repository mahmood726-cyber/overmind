@echo off
REM sentinel:skip-file — the OVERMIND_PYTHON fallback path on line 12 is a
REM Task-Scheduler-PATH workaround documented in lessons.md (2026-04-30):
REM scheduled tasks resolve PATH from the system-account profile, not the
REM interactive user profile, so bare `python` is often missing → exit
REM 2147942402 (ERROR_FILE_NOT_FOUND). The hardcoded absolute path is the
REM fix, not a portability bug. Override at runtime via OVERMIND_PYTHON env
REM var when needed (different machine, different Python install).
REM
REM Overmind Nightly Verifier — launched by Windows Task Scheduler
REM Runs at 3:00 AM daily, verifies up to 50 projects
REM
REM Uses `python` from PATH by default. Override with OVERMIND_PYTHON env var
REM if Task Scheduler's PATH doesn't include the intended interpreter.
REM Example: set OVERMIND_PYTHON to the full path of your Python 3.13 binary.

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

if "%OVERMIND_PYTHON%"=="" (set OVERMIND_PYTHON=C:\Users\user\AppData\Local\Programs\Python\Python313\python.exe)

"%OVERMIND_PYTHON%" "%~dp0nightly_verify.py" --limit 50 --timeout 120 --min-risk medium >> "%~dp0..\data\nightly_reports\nightly.log" 2>&1
