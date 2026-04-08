@echo off
REM Overmind Nightly Verifier — launched by Windows Task Scheduler
REM Runs at 3:00 AM daily, verifies up to 50 projects

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

"C:\Users\user\AppData\Local\Programs\Python\Python313\python.exe" "C:\overmind\scripts\nightly_verify.py" --limit 50 --timeout 120 --min-risk medium >> "C:\overmind\data\nightly_reports\nightly.log" 2>&1
