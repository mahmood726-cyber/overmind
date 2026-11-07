@echo off
REM Sets OVERMIND_PYTHON in the caller's environment, or exits 9.
REM Order: explicit OVERMIND_PYTHON, the per-user Python 3.13 install (the same
REM path install_overmind_task.ps1 checks), then python on PATH. Task Scheduler
REM PATH often lacks python, so PATH alone is not enough (lessons.md 2026-04-30).
REM A scheduled launcher must not start from a guessed path: a wrong default
REM stopped the nightly on 2026-05-17 with nothing raising an alert.

if defined OVERMIND_PYTHON goto :check

set "OVERMIND_PYTHON=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if exist "%OVERMIND_PYTHON%" goto :check

set "OVERMIND_PYTHON="
for /f "delims=" %%P in ('where python 2^>nul') do if not defined OVERMIND_PYTHON set "OVERMIND_PYTHON=%%P"
if not defined OVERMIND_PYTHON goto :missing

:check
if exist "%OVERMIND_PYTHON%" exit /b 0

:missing
>&2 echo [overmind] no usable Python: OVERMIND_PYTHON="%OVERMIND_PYTHON%"; set it to a Python 3.13 interpreter
exit /b 9
