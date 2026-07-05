# SOP — Gated Additive Deploy (shadow → enforce, one-flag rollback)

> **Version:** v1.1 · **Status:** governing principle of the workflow rollout plan · **Owner:** Overmind
> **Change log:** v1.0 — codified from the research doc §3 no-regression rollout + build-order discipline.
> v1.1 (2026-07-05) — added the **root-cause gate** for fixes (systematic-debugging, from `rules/debugging.md`);
> the objective-gate floor alone is necessary but not sufficient to accept a fix.

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

## Root-cause gate — before any FIX lands (systematic-debugging, adopted 2026-07-05)
When a shadow gate (Step 2) or a stop-condition surfaces a **failure or verdict delta**, the change that
resolves it is a *fix*, and a fix must clear the **root-cause GATE** before it is allowed to land
additively — the objective-gate floor ("it passes now") is necessary but **not sufficient** for a fix.

**The gate (all four before the fix is accepted):**
1. **Root cause stated.** You can name *what* is wrong and *why*, from the error/stack/`git diff`/boundary
   logs — not "it probably X". No fix without a root cause first. In a multi-boundary failure
   (CI→build→sign, lane→runner→store) add a diagnostic log at *each* boundary and run once to see *where*
   it breaks before touching a layer.
2. **Fixed at the source, not the symptom.** Trace backward from where the error surfaced to the original
   trigger; fix there. A validation added only at the symptom point is bypassed by the next code path —
   add defense-in-depth at each layer the bad value passes through (entry / logic / env-guard).
3. **Failing test first.** A test that reproduces the failure and is red *before* the fix, green *after* —
   this is the objective witness that the fix actually resolves the stated cause, not a coincidence.
4. **One fix, no stacking.** One hypothesis, smallest change, verify. Do **not** stack a second fix on an
   unverified first. **Stop at 3 failed fixes and question the architecture** — 3+ failing, or each fix
   revealing a new problem, is a wrong-architecture signal (surface it, do not attempt fix #4).

This subordinates fix-acceptance to *understanding*, closing the "symptom-patch in shadow, enforce anyway"
hole. Full discipline (four phases, backward tracing, defense-in-depth, rationalization table):
`rules/debugging.md`. Adapted from obra/superpowers (MIT, © 2025 Jesse Vincent / Prime Radiant).

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
  shadow, **diagnose through the root-cause gate above** (root cause stated → fixed at source → failing
  test first → one fix). Never enforce on an unmeasured path; never land a symptom-patch that merely
  makes the shadow log quiet without a named cause.

## Ties to
[[src-loop-engineering-cherny]] · [[src-scheduler-graph-sgh]] · [[src-lfd]] (constraints + instruments) ·
[[Single-Writer-Rule-SOP]] · [[_SOPs-MOC]].
