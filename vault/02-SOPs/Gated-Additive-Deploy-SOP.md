# SOP — Gated Additive Deploy (shadow → enforce, one-flag rollback)

> **Version:** v1.0 · **Status:** governing principle of the workflow rollout plan · **Owner:** Overmind
> **Change log:** v1.0 — codified from the research doc §3 no-regression rollout + build-order discipline.

## Purpose
Ship reliability/mechanism changes to a live verification stack **without ever silently moving a verdict**.
Every change is additive, flag-gated, and preceded by a measured zero-regression gate.

## The invariant
> **Every change is behind an env flag with the prior code path left intact for one full nightly cycle
> before the old path is removed.**

## Procedure (per mechanism)
1. **Land additively, behind a flag, in SHADOW (log-only).** Record what the new path *would* have done —
   what it would kill/retry/reject — without acting. Examples: `OVERMIND_SUBPROC_WATCHDOG` (shadow),
   `SENTINEL_RULE_TIMEOUT_MS` (unset = current), `OVERMIND_REQUIRE_CROSS_VENDOR_CHECK` (record-only).
2. **Measured zero-regression gate (A/B).** Run one full nightly + (for push-time rules) one week of
   pushes. The new path must show **zero verdict deltas** vs the old path — the only differences allowed are
   things that *would have hung/failed anyway*. For tightening gates, run as a **WARN cycle** first
   (`WOULD-SHIP-WITHOUT-OBJECTIVE-GATE`) to quantify impact before it blocks.
3. **Enforce.** Flip the flag to act only after the gate is green.
4. **Rollback = flip the flag.** The old path is untouched; nothing to unwind.

## Build-order discipline (Boris Cherny / [[src-loop-engineering-cherny]])
**manual-reliable → Skill → loop(gate+stop) → then schedule.** Nothing gets scheduled before it is reliable
by hand. Direct check: the still-unmerged cluster branch must not be *scheduled* before it is merged /
CI-proven.

## Bounded recovery ceiling ([[src-scheduler-graph-sgh]] escalation)
Wrap retries in the three-level ceiling: L1 bounded Retry (transient) → L2 Local Patch → L3 Replan — so
recovery **terminates** instead of looping (stops requeue storms). Pairs with per-subprocess/per-node hard
stops.

## Objective gate
Non-empty shadow logs for one nightly + a recorded zero-verdict-delta comparison **before** any flag flips
to enforce. Portable paths first (Step 0: no hardcoded `C:/overmind/...`) so shadow can run off-`C:`.

## Stop conditions
- **Success:** measured zero-regression → enforce.
- **Failure:** any verdict delta the new path introduces that isn't a would-have-failed case → stay in
  shadow, diagnose. Never enforce on an unmeasured path.

## Ties to
[[src-loop-engineering-cherny]] · [[src-scheduler-graph-sgh]] · [[src-lfd]] (constraints + instruments) ·
[[Single-Writer-Rule-SOP]] · [[_SOPs-MOC]].
