# Multi-Persona Review: session-2026-05-06 infrastructure changes
### Date: 2026-05-06
### Scope: 6 commits across overmind / Sentinel / E156
### Reviewers: 8 blinded personas (Statistical, Security, Software Eng, Domain Expert, SRE, Concurrency, Test Coverage, Red-Team)
### Summary: 8 P0, 16 P1, 9 P2 (after dedup across personas)

---

## P0 — Critical (must fix before next nightly)

- **[P0-1]** Statistical: `data/baselines/patientma-a0324dc7.json` ppf_0.975=1.960395 vs canonical z_{0.975}=1.9599639845 (scipy / R / Wichura AS241). Discrepancy 4.3e-4 exceeds declared tolerance 1e-4 by 4.3x. Either PatientMA's PPF probe runs a buggy approximation (Beasley-Springer-Moro short-form?) and this baseline now PINS the bug, or the value was hand-typed. Every 95% CI built with this PPF is too wide by ~0.022%.
  - Fix: re-run probe against scipy.stats.norm.ppf; if PatientMA still emits 1.960395, that's a P0 in PatientMA itself, not a baseline-tolerance miss.

- **[P0-2]** Domain Expert + Red-Team (DOUBLE FLAG): commit `b94f34d` advertised as "denominator normalization" but bundles a substantive **CURRENT BODY rewrite of entry 5 (AfricaRCT)** — TITLE / TYPE / ESTIMAND / DATA / PATH / 156-word body all replaced — plus a new entry 678 (pactr-hiddenness-atlas) inserted. Net diff is dominated by `[N/549]→[N/678]` cosmetic noise (762 ins / 675 del), making the body change invisible to skim review. **Verified via `git show b94f34d`.** This is the smuggle-via-cosmetic-diff pattern lessons.md flags. The commit is already pushed; can't unbundle without history rewrite.
  - Fix forward: add a pre-commit check that fails when a single commit touches both `[N/X]` denominators AND a `CURRENT BODY:` or `YOUR REWRITE:` line. Document the bundling in a new lessons.md entry so the pattern doesn't recur.

- **[P0-3]** SRE: **NO ALERTING.** Nightly logs to `nightly.log`, writes JSON to disk, but nothing pages or emails on FAIL / missing-report / non-zero exit. After the 2026-05-04 freeze the operator only discovered it 3 days later. Recovery time without external alerting = unbounded.
  - Fix: 08:00 scheduled watchdog asserting (a) `nightly_<yesterday>.json` exists, (b) `partial != true`, (c) timestamp within 24h. Push Windows toast / email / dashboard write on failure.

- **[P0-4]** SRE: Task Scheduler Action lacks `MultipleInstances IgnoreNew` (or `StopExisting`). lessons.md 2026-04-30 documents this as the exact mitigation for the `2147946720 / ERROR_SERVICE_ALREADY_RUNNING` exit code. The scheduled-task XML/install script is NOT in the repo, so the mitigation is undocumented and unverifiable. Without this, the 3-day outage recurs on next hang.
  - Fix: commit `scripts/install_overmind_task.ps1` that creates the Action with `MultipleInstances IgnoreNew` + idle-condition + working-dir.

- **[P0-5]** Concurrency: `path.write_text()` is **non-atomic on Windows** in three hot-path call sites:
  - `nightly_verify.py:289` partial-report write (per-iteration)
  - `nightly_verify.py:886` `.progress_<date>.json` write (per-iteration)
  - `nightly_verify.py:878` per-project bundle JSON write
  
  Concurrent invocation (manual rerun + scheduler, or scheduler + a second manual) tears the file → `json.loads` raises → falls into bare-except → silent overwrite. The "don't clobber canonical" guarantee at line 246 is defeated by any read that races a write. With 50 projects × ~50 bundles per night = up to 250 writes per night to shared files.
  - Fix: write-temp-then-rename via `os.replace` (atomic on NTFS same-volume): `tmp = path.with_suffix('.tmp'); tmp.write_text(...); os.replace(tmp, path)`.

- **[P0-6]** Test Coverage: `_promote_progress_to_partial_report` has **zero tests**. 70 lines of defensive code with three explicit documented invariants ("never raises", "idempotent on full success", "covers exception paths even when faulthandler does not fire") and no test verifies any of them. The fix-and-ship-without-TDD signature.
  - Fix: add `tests/unit/test_partial_report_promotion.py` covering: (a) no progress → no-op; (b) progress + bundles → partial:true + tally matches; (c) idempotency: pre-existing canonical NOT overwritten; (d) pre-existing partial IS overwritten with newer counts; (e) malformed progress → swallowed; (f) bundles missing → projects:[]; (g) monkeypatched-raising-json.loads → still doesn't raise.

- **[P0-7]** Test Coverage: No integration test for atexit + per-iteration partial-write end-to-end. The whole defensive design (faulthandler `_exit` bypasses atexit/finally → per-iteration write is the safety net) is asserted only in comments. The next regression that reorders the per-iteration call gets caught in production, not CI.
  - Fix: integration test that spawns nightly_verify with a stubbed engine that raises mid-loop, asserts `partial:true` report on disk afterward.

- **[P0-8]** Red-Team + Test Coverage (DOUBLE FLAG): `_file_has_skip_marker` does substring scan `"sentinel:skip-file" in head` over first 1024 bytes with NO word-boundary check, NO audit log, NO portfolio-wide reconciliation. False-suppresses on any string containing the marker as substring (`xsentinel:skip-file`, `// not-sentinel:skip-file`). An attacker pre-pending `# sentinel:skip-file` to every malicious .py/.js bypasses parse-check silently with no signal in the verdict report.
  - Fix: anchor marker to column 0 of line 1 with delimiter regex `^[#/* ]+sentinel:skip-file\b`; emit a WARN-severity Verdict every time the marker is honored (`P2-skip-marker-honored` rule) so portfolio reconciliation can audit growth.

---

## P1 — Important (should fix this week)

- **[P1-1]** SE: `_file_has_skip_marker` byte-identical duplicate in `js_parse_check.py:116-121` and `py_parse_check.py:105-110`. Real DRY violation — any fix to one (BOM handling, larger window, line-anchored marker) silently diverges. Extract to `sentinel/io/skip_marker.py`.

- **[P1-2]** SE: `_promote_progress_to_partial_report` swallows ALL exceptions silently. Lessons.md "Confident-tone tool failures are invisible" applies — a bug here leaves the operator with no signal. Log exception class+message to `crash_<date>.log` before silent return.

- **[P1-3]** SE: per-iteration flush is O(N²) — 50 projects × up to 50 bundles glob = ~2,500 reads. Estimated cost ~10-30s on a populated bundles dir, not the 2.5s claimed. Re-use in-process progress dict + running list of bundle records.

- **[P1-4]** SE + Test Coverage + Concurrency (TRIPLE FLAG): dedup key `(rid, file, line)` mixes types. `obj.get("line", "")` accepts int 42 and str "42" as DIFFERENT keys. If Sentinel writers ever emit either form (cross-version drift), dedup fragmentation re-introduces the 9.2x amplification. Coerce: `str(obj.get("line", ""))`.

- **[P1-5]** Domain Expert: workbook denominator-semantics convention switch is undocumented. The previous lessons.md entry treated drift as the bug; the new commit treats uniform-now as canonical. Both defensible but the convention shift should be in the workbook header so the next normalization sweep isn't re-flagged. Add: `Denominator convention: [N/total-as-of-last-reconcile]; back-rewritten on milestone boundaries.`

- **[P1-6]** Security: baseline JSON's `command` field IS executed via `subprocess.run(split_command(command), shell=False, cwd=cwd)`. Allowlist accepts ANY absolute Windows executable matching `^\s*"?[A-Za-z]:\\`. A baseline with `command: "C:/Windows/System32/wscript.exe attacker.vbs"` would pass. Tighten `WINDOWS_ABSOLUTE_EXECUTABLE_RE` to require basename mapping into `ALLOWED_COMMAND_PREFIXES`; add a Sentinel WARN-rule on `data/baselines/*.json` asserting `command` parses to allowlisted basename.

- **[P1-7]** Security + Domain Expert (DOUBLE FLAG): skip-marker scope laxness — accepted anywhere in first 1024 bytes (not anchored), no rule-level audit of which files carry it. Pairs with [P0-8].

- **[P1-8]** SRE: `dump_traceback_later(14400, exit=True)` is 4h, but per-project budget × `--limit 50` = 25h theoretical max. Two PROJECT_WORKER_TIMEOUTS-bumped projects (rct-extractor-v2 + evidence-inference @ 7200s each) alone = 7.2h > 4h cap. The script `_exit()`s mid-run on any night that schedules both. Either raise the cap to ~28800s OR document explicitly that 4h truncation is the contract and partial report IS the deliverable.

- **[P1-9]** SRE: `crash_<date>.log` is written ONLY when `_run_verification` raises. faulthandler `_exit` (the actual 2026-05-04 failure mode) bypasses the except block — no crash log was written for the incident this fix is meant to handle. Need pre-exit hook (write `faulthandler_<date>.log` from inside the loop when wall-clock approaches 14400s) OR redirect faulthandler output via `faulthandler.enable(file=...)` to a persistent path.

- **[P1-10]** SRE: no "task launched cleanly" smoke. Operator can't validate at 03:05 that the run started; must wait until 08:00. Add `nightly_started_<date>.flag` file written at top of `_run_verification` so health-checks can distinguish "didn't start" from "started but hung".

- **[P1-11]** SRE: No `RUNBOOK.md`. Recovery flow (Stop-ScheduledTask, trigger fresh run, check `.progress` for last project, optionally `--projects-from-file` rerun) is buried in lessons.md and SKIP_PROJECTS comments.

- **[P1-12]** SRE: `Stop-ScheduledTask` is asymmetric — stops the task definition, not necessarily the orphan python.exe child holding inherited pipe handles. Run-book must include `Get-Process python | Where-Object {...}` + targeted `Stop-Process` for confirmed-orphan PIDs.

- **[P1-13]** SRE: dedup landing isn't observable in CI. Add an assertion in the report writer ("if total_block > 30000 emit WARN to stderr") so regression to N-fold counting is detectable without manual diff.

- **[P1-14]** Test Coverage: dedup tests cover only happy path. Missing: (a) `line: null` vs `line: 0` vs `line: "0"`; (b) `file` missing entirely on both sides; (c) malformed-JSON line **interleaved** with duplicate findings (composition test); (d) per-repo scoping (cross-repo isolation).

- **[P1-15]** Red-Team: `.progress_*.json` planting attack — file is gitignored, so a planted file with crafted verdicts is invisible in `git status`. First iteration reads it as `completed_ids`, skips real verification, writes a partial report endorsing planted verdicts. HMAC the progress map (key from env, never bundle-derived per crypto lesson); refuse to skip projects whose progress entry has no matching `bundles/<date>/<id>.json`.

- **[P1-16]** Red-Team: empty-coords dedup collision. Attacker writes finding with `file=""`, `line=""` — collapses into the SAME bucket as any other empty-coords finding. P0 hides behind WARN. Treat empty `file` as `f"_norepo_{uuid}"` so empty-coords never collide.

---

## P2 — Minor (nice to fix)

- **[P2-1]** Domain Expert: bayesian-ma baseline pins file-stats only (size_kb, n_lines), not Bayesian math. Should probe at least one Bayesian-specific scalar (Rhat ≤ 1.01, ESS ≥ 400 per advanced-stats.md, posterior mean of fixed example). Current baseline passes even if every Bayesian computation returns NaN.

- **[P2-2]** Domain Expert: patientma tolerance 0.0001 too loose for analytic CDF (true 0.97500210...). Tighten to 1e-6.

- **[P2-3]** Domain Expert: Sentinel WARN (not BLOCK) rule `P2-skip-file-inventory` listing every file carrying `sentinel:skip-file` in `sentinel-findings.md` — same audit-trail pattern as bypass.log. Pairs with [P0-8].

- **[P2-4]** Security: `crash_*.log` contains `traceback.format_exc()` which can include `os.environ` snapshots, local variables. Scrub `C:\Users\<user>` → `<home>` before write.

- **[P2-5]** Security: `.gitignore` `data/nightly_reports/.progress_*.json` broad enough that a future contributor's `.progress_summary.json` would be silently ignored. Tighten to `.progress_20[0-9][0-9]-[0-9]*.json`.

- **[P2-6]** Concurrency: `bundle_path.write_text` (line 878) also non-atomic. Apply same `os.replace` fix.

- **[P2-7]** SE: `from collections import Counter` hoisted to module top (currently inside hot-path helper).

- **[P2-8]** SRE: gitignoring `crash_*.log` loses incident forensic trail. Compromise: keep ignored in `data/nightly_reports/` but auto-copy last 30 days into a tracked `docs/incidents/` dir on each nightly.

- **[P2-9]** SRE: no nightly-over-nightly delta in report. Add `delta_from_previous: {total_block_change: -126000}` so 9.2x dedup landing is observable.

---

## False positives avoided (good design verified)

- **atexit semantics doc accurate** [SE]: atexit DOES fire on `sys.exit()` and unhandled exceptions; does NOT on `os._exit()`/SIGKILL/segfault. The faulthandler `exit=True` path uses `_exit`, so the per-iteration write IS the real safety net as documented.
- **Idempotency check correct** [SE, Concurrency]: line 246 reads existing `partial` flag; canonical write at 1241 omits the flag entirely so the helper correctly returns early on canonical reports.
- **BCG canonical fixture values match metafor** [Domain Expert]: superapp τ²_REML=0.313243 with k=13 matches `dat.bcg` to 4dp; PET/PEESE intercepts plausible.
- **patientma cdf_1.96=0.975002, cdf_0.0=0.5, cdf_-1.0=0.158655** match scipy to declared tolerance [Statistical] (only ppf_0.975 is wrong).
- **subprocess shell=False + allowlist intact for relative commands** [Security]: only the absolute-path branch is the gap.
- **multiprocessing kill_tree** [Concurrency]: correctly applies lessons.md mitigation (psutil.children(recursive=True) + child.kill() before worker.terminate()).
- **No SUBMITTED markers were touched** in workbook commit [Domain Expert]: 0 `-SUBMITTED:` removals; only `+SUBMITTED: [ ]` for new entry 678.
- **SUMMITTED rule + YOUR REWRITE protection** [Red-Team, Domain Expert]: workbook diff doesn't violate "NEVER touch YOUR REWRITE" — but commit-scope mismatch is the P0.

---

## Recommended fix order

1. **P0-1** (patientma ppf bug) — pin a probe re-run; can ship in 30 min
2. **P0-5** (atomic Windows writes) — one-line per call site, three call sites
3. **P0-6 + P0-7** (test coverage for partial-report flush) — 1-2 hours
4. **P0-8** (skip-marker word-boundary + audit) — 30 min
5. **P0-3 + P0-4** (alerting + MultipleInstances) — half day; biggest operational lift
6. **P0-2** (commit-scope guard pre-commit hook) — 1 hour
7. P1 cluster — week of work; group [P1-1]+[P0-8]+[P1-7]+[P2-3] as the skip-marker hardening epic; group [P1-3]+[P1-4]+[P1-14] as the dedup-correctness epic; group [P1-8]+[P1-9]+[P1-10]+[P1-11]+[P1-12]+[P1-13] as the SRE-observability epic
8. P2 cleanup
