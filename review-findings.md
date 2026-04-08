## Multi-Persona Review: AutoFixer + Nightly Timeout
### Date: 2026-04-08
### Scope: remediation/auto_fixer.py, remediation/strategies.py, subprocess_utils.py, nightly_verify.py
### Status: REVIEW CLEAN
### Test suite: 195/195 pass
### Summary: 2 P0 (FIXED), 4 P1 (FIXED), 2 P2 (advisory)

#### P0 — Critical

- **[P0-1]** [Security+SWE] `git add -A` in auto_fixer.py:159 stages everything — .env, secrets, binaries. (auto_fixer.py:159)
  - Fix: [FIXED] Removed git commit entirely. AutoFixer should only fix the environment, not commit. Let the nightly report flag what was fixed; human reviews before pushing.

- **[P0-2]** [Security] pip install from unvalidated module name extracted from stderr. No allowlist of permitted packages. (strategies.py:42-44)
  - Fix: [FIXED] Added re.fullmatch validation + pip install --dry-run first. Log the install but don't auto-commit.

#### P1 — Important

- **[P1-1]** [SWE] Unhandled JSONDecodeError in BaselineDriftFix when baseline file is corrupt. (strategies.py:111)
  - Fix: [FIXED] Wrapped in try/except with FixResult(False).

- **[P1-2]** [SWE] multiprocessing.Queue never closed/joined — pipe handle leak on Windows. (nightly_verify.py:122-155)
  - Fix: [FIXED] Added _cleanup_queue() helper called on all paths.

- **[P1-3]** [Security] Path traversal in MissingFixtureFix — `..` in extracted path. (strategies.py:149-160)
  - Fix: [FIXED] Path.resolve() + startswith check.

- **[P1-4]** [Security] No delta bounds-checking on baseline updates — probe could return wildly different values. (strategies.py:93-114)
  - Fix: [FIXED] Rejects if any numeric value changes >50%.

#### P2 — Minor

- **[P2-1]** [SWE] --allow-empty on git commit permits empty commits. (auto_fixer.py:172)
- **[P2-2]** [Security] LOCAL_MODULE_PATTERNS covers only 10 of 276+ project modules. (strategies.py:30-33)

#### False Positive Watch
- The closure in make_verify_fn is correct (confirmed by SWE reviewer)
- shlex.split posix=True: already tested working with 195/195 tests on Windows
