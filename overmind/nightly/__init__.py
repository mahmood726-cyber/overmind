"""Overmind nightly verifier — extracted submodules.

This package was carved out of `scripts/nightly_verify.py` (1655-LOC
monolith) as Phase-3 workstream M. The original script remains the
entry point; the submodules here hold the reusable helpers it
previously defined inline. `nightly_verify.py` re-imports the public
surface so the test fixtures that reach for
`nightly_verify.<name>` continue to work unchanged.

Submodules:
- paths        — DATA_DIR / REPORT_DIR / DB_PATH constants
- reporting    — _atomic_write_text, _promote_progress_to_partial_report,
                 _report_paths, _existing_path_arg, _scrub_user_paths
- selection    — SKIP_PROJECTS, PROJECT_WORKER_TIMEOUTS, _normalize_path,
                 load_paths_filter, select_projects
- integrations — collect_sentinel_findings, collect_bypass_findings,
                 _run_portfolio_sentinel_scan

Phase 4 will extract the remaining 820-LOC `_run_verification` driver
(workstream M-2) after a byte-identical-bundle snapshot is captured for
one fixture project.
"""
