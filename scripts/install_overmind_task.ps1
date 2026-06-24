#requires -Version 5
<#
.SYNOPSIS
  Install the Overmind Nightly Verifier + Morning Watchdog scheduled tasks.

.DESCRIPTION
  Per the 8-persona blinded review (P0-4 SRE): the prior incarnation of
  the task was missing `MultipleInstances IgnoreNew`, which caused the
  2026-05-04 freeze (one stuck instance held the slot for 3 days at exit
  code 0x80070420 / ERROR_SERVICE_ALREADY_RUNNING). lessons.md 2026-04-30
  documents this exact mitigation.

  This script installs three tasks:
    1. "Overmind Nightly Verifier"      — daily at 03:00, IgnoreNew on collision
    2. "Overmind Morning Watchdog"      — daily at 08:00, alerts if last night failed
    3. "Overmind Memory Consolidation"  — weekly (Sun 04:00), deterministic
                                          markdown-memory decay/consolidation pass

.PARAMETER User
  The user the task runs as. Defaults to current user. Must be the owner of
  the Python install referenced by OVERMIND_PYTHON.

.EXAMPLE
  PS> .\install_overmind_task.ps1
  Installs both tasks with default times.

.NOTES
  Re-running is idempotent — Unregister-ScheduledTask is called first
  to avoid duplicate-name errors.
#>
param(
    [string]$User = "$env:USERDOMAIN\$env:USERNAME"
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$nightlyBat = Join-Path $repoRoot 'scripts\nightly_verify.bat'
$watchdogPy = Join-Path $repoRoot 'scripts\morning_watchdog.py'
$consolidateBat = Join-Path $repoRoot 'scripts\consolidate_memory.bat'
$python = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"

if (-not (Test-Path $nightlyBat))     { throw "missing: $nightlyBat" }
if (-not (Test-Path $watchdogPy))     { throw "missing: $watchdogPy" }
if (-not (Test-Path $consolidateBat)) { throw "missing: $consolidateBat" }
if (-not (Test-Path $python))         { throw "missing: $python (set OVERMIND_PYTHON if installed elsewhere)" }

# === Nightly Verifier ===
$nightlyAction = New-ScheduledTaskAction -Execute $nightlyBat -WorkingDirectory $repoRoot
$nightlyTrigger = New-ScheduledTaskTrigger -Daily -At 03:00am
$nightlySettings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 5) `
    -RestartCount 0 `
    -StartWhenAvailable
$nightlyPrincipal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited

Unregister-ScheduledTask -TaskName 'Overmind Nightly Verifier' -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask `
    -TaskName 'Overmind Nightly Verifier' `
    -Action $nightlyAction `
    -Trigger $nightlyTrigger `
    -Settings $nightlySettings `
    -Principal $nightlyPrincipal `
    -Description ('Runs nightly_verify.py at 03:00. MultipleInstances=IgnoreNew per ' +
                  'lessons.md 2026-04-30 (prevents ERROR_SERVICE_ALREADY_RUNNING).')
Write-Host "Installed: Overmind Nightly Verifier (03:00 daily, IgnoreNew on collision)"

# === Morning Watchdog ===
$watchdogAction = New-ScheduledTaskAction `
    -Execute $python `
    -Argument $watchdogPy `
    -WorkingDirectory $repoRoot
$watchdogTrigger = New-ScheduledTaskTrigger -Daily -At 08:00am
$watchdogSettings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
    -StartWhenAvailable

Unregister-ScheduledTask -TaskName 'Overmind Morning Watchdog' -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask `
    -TaskName 'Overmind Morning Watchdog' `
    -Action $watchdogAction `
    -Trigger $watchdogTrigger `
    -Settings $watchdogSettings `
    -Principal $nightlyPrincipal `
    -Description ('Asserts last night''s nightly_<date>.json exists, is not partial, ' +
                  'and total_block did not regress past dedup threshold. Toast on failure.')
Write-Host "Installed: Overmind Morning Watchdog (08:00 daily)"

# === Memory Consolidation (audit C3 / A5) ===
# Weekly deterministic consolidation: archives expired/stale markdown facts
# (reversible) and logs the dedup/orphan/non-current report. Sunday 04:00 — after
# the nightly verifier (03:00) so it never contends for the same window.
$consolidateAction = New-ScheduledTaskAction -Execute $consolidateBat -WorkingDirectory $repoRoot
$consolidateTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 04:00am
$consolidateSettings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -StartWhenAvailable

Unregister-ScheduledTask -TaskName 'Overmind Memory Consolidation' -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask `
    -TaskName 'Overmind Memory Consolidation' `
    -Action $consolidateAction `
    -Trigger $consolidateTrigger `
    -Settings $consolidateSettings `
    -Principal $nightlyPrincipal `
    -Description ('Weekly deterministic markdown-memory consolidation (Sun 04:00): ' +
                  'archives expired/stale facts to <memory>/archive/ (reversible) and ' +
                  'logs near-duplicate/orphan-link/non-current report. Reflective LLM ' +
                  'consolidate-memory skill remains a manual pass.')
Write-Host "Installed: Overmind Memory Consolidation (Sun 04:00 weekly)"
Write-Host ""
Write-Host "Verify: Get-ScheduledTask -TaskName 'Overmind*' | Format-Table TaskName,State,LastRunTime"
