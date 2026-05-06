# Overmind Operations Runbook

> When to read this: the Morning Watchdog raised an alert, or you woke up to a
> failed/missing nightly. Recovery here goes from "5 minutes if you know
> what to look at" to "an hour or more if you don't."

## Daily schedule

| Time | Task | What it does |
|------|------|---|
| 03:00 | `Overmind Nightly Verifier` | Runs `--limit 50 --worker-timeout 1800 --min-risk medium`. Writes `data/nightly_reports/nightly_<YYYY-MM-DD>.json` + `.md` + `bundles/<date>/<id>.json` per project. |
| 08:00 | `Overmind Morning Watchdog` | Asserts last night's report exists, is non-partial, has fresh timestamp, and `sentinel.total_block` did not regress past 30K. Toast + writes `watchdog_<today>.alert` on failure. |

## Files you'll look at when something is wrong

- `data/nightly_reports/nightly_<date>.json` — the canonical report. Has `partial: true` if main loop didn't reach end.
- `data/nightly_reports/.progress_<date>.json` — per-iteration crash-resume state. Cleaned on success, persists on kill.
- `data/nightly_reports/crash_<date>.log` — written by `main()`'s except-handler OR by `_promote_progress_to_partial_report` when it swallowed an exception (P1-2).
- `data/nightly_reports/nightly.log` — stdout/stderr tail of the actual run. Often the most useful single file.
- `data/nightly_reports/bundles/<date>/<id>.json` — per-project verdict bundles.
- `data/nightly_reports/watchdog_<today>.alert` — written by morning watchdog when it raised an alert.

## Symptom → diagnosis

### A: Watchdog alert says `nightly_<yesterday>.json missing`

The scheduled run didn't complete (or didn't start). Check:

```pwsh
Get-ScheduledTaskInfo -TaskName "Overmind Nightly Verifier" |
    Select-Object TaskName, LastRunTime, LastTaskResult, NextRunTime
```

`LastTaskResult` interpretation:
- `0` — succeeded; report should exist (if not, check `nightly.log` for crash + `crash_<date>.log`)
- `2147946720` (= `0x80070420` ERROR_SERVICE_ALREADY_RUNNING) — previous instance hung, never released the slot. Recovery: see [B].
- `2147942402` (= `0x80070002` ERROR_FILE_NOT_FOUND) — Python interpreter not on Task Scheduler PATH. Set `OVERMIND_PYTHON` env var. See lessons.md 2026-04-30.
- Other non-zero — check `nightly.log` for the actual crash.

### B: Stuck instance / `ERROR_SERVICE_ALREADY_RUNNING`

```pwsh
# 1. Stop the scheduler's view
Stop-ScheduledTask -TaskName "Overmind Nightly Verifier"

# 2. Check for orphan python.exe holding pipe handles (lessons.md 2026-04-30)
Get-Process python -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like "*Python313*" } |
    Format-Table Id, StartTime, Path

# 3. If any python.exe shows StartTime older than your last successful run,
#    that's the orphan. Kill its process tree:
Stop-Process -Id <PID> -Force

# 4. Optionally trigger a fresh run (or just wait for tomorrow's 03:00):
Start-ScheduledTask -TaskName "Overmind Nightly Verifier"
```

### C: Watchdog alert says `partial: true`

The run started but `_run_verification` didn't reach the canonical end-of-run write. Possible causes:

1. **Faulthandler safety-net fired** (4h cap). The most recent `.progress_<date>.json` has the verdicts that DID complete. Check `nightly.log` tail for the project that was running at the moment of `_exit`.
2. **Unhandled exception** — check `crash_<date>.log`.
3. **kill -9 / power loss** — no log; rely on `.progress_<date>.json`.

Recovery: identify the offending project, decide whether to add to `SKIP_PROJECTS` in `scripts/nightly_verify.py` (with a comment per the existing convention) or extend its `PROJECT_WORKER_TIMEOUTS`. Then `--projects-from-file` rerun the unfinished projects against the same date — the partial-report-flush will be overwritten by the canonical write when the rerun completes.

### D: Watchdog alert says `total_block exceeded threshold`

Sentinel dedup may have regressed (rule_id schema drift, new key-coercion bug, or a real explosion in violations across the portfolio).

```pwsh
# Re-run the aggregator standalone:
cd C:\overmind
python -c "from overmind.integrations.sentinel_aggregator import collect; import json; print(json.dumps(collect(), indent=2)[:2000])"
```

Compare `top_repos` against last week's. A single-repo spike is usually a real violation cluster (push BLOCKs there); a uniform increase across all repos suggests dedup regression — `git log overmind/integrations/sentinel_aggregator.py` for recent changes.

### E: A specific project is hanging

One project chewing through `--worker-timeout` repeatedly:

```pwsh
# See which project is currently running:
Get-Content C:\overmind\data\nightly_reports\nightly.log -Tail 5

# Probe the witnesses individually for the hanging project to isolate:
cd C:\overmind
# (replace mem-ecosystem-model-8299ceea with the actual id)
python -c "
import sqlite3, json, time
from pathlib import Path
con = sqlite3.connect('data/state/overmind.db')
payload = json.loads(con.execute('SELECT payload FROM projects WHERE id=?', ('PROJECT_ID',)).fetchone()[0])
from overmind.storage.models import ProjectRecord
proj = ProjectRecord(**payload)
from overmind.verification.truthcert_engine import TruthCertEngine
engine = TruthCertEngine(baselines_dir=Path('data/baselines'), test_timeout=120)
for w in ['test_suite_witness','smoke_witness','semgrep_witness','pip_audit_witness']:
    t=time.time(); r=getattr(engine,w).run(...); print(w, r.verdict, time.time()-t)
"
```

Decide: SKIP (transient/network), `PROJECT_WORKER_TIMEOUTS` bump (legit slow), or fix-the-project.

## When to escalate to repo-edit

If the recovery above doesn't unstick the run within ~30 min, edit `scripts/nightly_verify.py` (or relevant project) and let the next 03:00 run pick it up. Avoid hot-fixing in production hours unless the next morning's run can't recover.

## See also

- `lessons.md` — past-incident patterns (Task Scheduler exit codes, multiprocessing kill-tree on Windows, faulthandler `_exit` bypassing atexit).
- `review-findings-session-2026-05-06.md` — 8-persona blinded review that motivated this runbook.
