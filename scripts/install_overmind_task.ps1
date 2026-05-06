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

  This script installs both:
    1. "Overmind Nightly Verifier" — daily at 03:00, IgnoreNew on collision
    2. "Overmind Morning Watchdog" — daily at 08:00, alerts if last night failed

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
$python = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"

if (-not (Test-Path $nightlyBat)) { throw "missing: $nightlyBat" }
if (-not (Test-Path $watchdogPy)) { throw "missing: $watchdogPy" }
if (-not (Test-Path $python))     { throw "missing: $python (set OVERMIND_PYTHON if installed elsewhere)" }

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
Write-Host ""
Write-Host "Verify: Get-ScheduledTask -TaskName 'Overmind*' | Format-Table TaskName,State,LastRunTime"
