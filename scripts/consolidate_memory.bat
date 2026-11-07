@echo off
REM Overmind Memory Consolidation — launched by Windows Task Scheduler.
REM Deterministic markdown-memory consolidation pass (audit C3 / A5):
REM   - archives expired (valid_until past) / >365d-stale facts to <memory>/archive/
REM     (reversible move, never deletes, never edits)
REM   - logs the consolidation report (near-duplicates, orphan [[links]],
REM     non-current/superseded facts, files missing from MEMORY.md) for review
REM
REM This is the unattended *deterministic* pass. The reflective LLM
REM `consolidate-memory` skill (merge/rewrite) stays a manual, interactive pass.

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

call "%~dp0resolve_python.bat" >> "%~dp0..\data\nightly_reports\consolidate_memory.log" 2>&1
if errorlevel 1 exit /b 9

"%OVERMIND_PYTHON%" -m overmind.cli notes consolidate --apply >> "%~dp0..\data\nightly_reports\consolidate_memory.log" 2>&1
