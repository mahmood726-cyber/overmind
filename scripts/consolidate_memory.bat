@echo off
REM sentinel:skip-file — same OVERMIND_PYTHON Task-Scheduler-PATH workaround as
REM nightly_verify.bat (see lessons.md 2026-04-30): scheduled tasks resolve PATH
REM from the system-account profile, so the hardcoded absolute fallback is the
REM fix, not a portability bug. Override with the OVERMIND_PYTHON env var.
REM
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

if "%OVERMIND_PYTHON%"=="" (set OVERMIND_PYTHON=C:\Users\user\AppData\Local\Programs\Python\Python313\python.exe)

"%OVERMIND_PYTHON%" -m overmind.cli notes consolidate --apply >> "%~dp0..\data\nightly_reports\consolidate_memory.log" 2>&1
