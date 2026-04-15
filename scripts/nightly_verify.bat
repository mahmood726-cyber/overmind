@echo off
REM Overmind Nightly Verifier — launched by Windows Task Scheduler
REM Runs at 3:00 AM daily, verifies up to 50 projects
REM
REM Uses `python` from PATH by default. Override with OVERMIND_PYTHON env var
REM if Task Scheduler's PATH doesn't include the intended interpreter.
REM Example: set OVERMIND_PYTHON to the full path of your Python 3.13 binary.

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

if "%OVERMIND_PYTHON%"=="" (set OVERMIND_PYTHON=python)

"%OVERMIND_PYTHON%" "%~dp0nightly_verify.py" --limit 50 --timeout 120 --min-risk medium >> "%~dp0..\data\nightly_reports\nightly.log" 2>&1
