@echo off
REM Overmind Nightly Verifier — launched by Windows Task Scheduler
REM Runs at 3:00 AM daily, verifies up to 50 projects
REM
REM Interpreter resolution and its failure mode live in resolve_python.bat.

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

call "%~dp0resolve_python.bat" >> "%~dp0..\data\nightly_reports\nightly.log" 2>&1
if errorlevel 1 exit /b 9

REM --worker-timeout 1800 (was default 900): rct-extractor-v2 has 851 tests +
REM semgrep on a 30K-line codebase, evidence-inference has a heavy deps tree.
REM Their combined witness pipelines exceed 900s. 1800s is a ceiling, not an
REM average — most projects still complete in <60s.
"%OVERMIND_PYTHON%" "%~dp0nightly_verify.py" --limit 50 --timeout 120 --worker-timeout 1800 --min-risk medium >> "%~dp0..\data\nightly_reports\nightly.log" 2>&1
