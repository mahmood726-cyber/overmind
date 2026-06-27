# Overmind Loop Charter — {date}

## GOAL
Measurable done condition: {goal}

Fixpoint check: all high-risk projects CERTIFIED or circuit-open (no project
left in FAIL/REJECT that still has remaining repair budget).

## WHERE THE WORK IS
Projects: {project_count} selected, path filter: {paths_filter}
Risk floor: {min_risk}
Limit: {limit}

## HOW TO WORK
Runner: scripts/nightly_verify.py --limit {limit} --budget-usd {budget_usd} --min-risk {min_risk}
Add --manual for a human-initiated run (satisfies manual_run_required gate).
Add --unsafe-fixes to allow fix types beyond the SAFE_FIX_ACTIONS allowlist.

## HOW TO CHECK YOURSELF
Witnesses required: test_suite + smoke + (tier-3) numerical.
Judge: QuorumJudge (cross-family, enforce_different_family=ON by default).
Measurable bar: CERTIFIED verdict — not "tests pass", not "judge returned PASS".
UNVERIFIED (missing baseline) is NOT a pass; do not promote until baseline exists.

## HOW TO REMEMBER
State file:     data/LOOP-STATE_{date}.md  — read at start, written after each project
Crash-resume:   data/.progress_{date}.json — atomic, survives os._exit
Circuit states: data/circuit_states.json   — persists across nights
Needs-me:       data/NEEDS_ME_{date}.md    — non-blocking; items await human action

## WHEN TO STOP
- **Done**: all high-risk projects CERTIFIED or circuit-open; GoalChecker returns YES
- **Blocked**: circuit-open count > {circuit_threshold}; NEEDS_ME_{date}.md lists them;
  LLM repair phase halted; loop pauses — human must clear before next iteration
- **Needs-me**: items in NEEDS_ME_{date}.md require human authorization
  (spend money, delete, push with bypass, manual baseline creation)
- **Budget hit**: --budget-usd ceiling reached; LLM phase halts; whole run continues

## SAFETY RAILS ACTIVE
- NightCircuitBreaker: trips after 3 consecutive FAIL nights → OPEN → skip
- ItemRetryCounter: 3 repair attempts per project per run → NEEDS_ME, move on
- SAFE_FIX_ACTIONS: auto-fix restricted to BASELINE_UPDATE/FLOAT_PRECISION/FORMULA_ERROR
  unless --unsafe-fixes is set
- OVERMIND_AUTOFIXER_WORKTREE: set to 1 to require git worktree isolation for writes
