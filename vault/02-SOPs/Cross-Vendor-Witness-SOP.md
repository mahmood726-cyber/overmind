# SOP — Cross-Vendor Witness

> **Version:** v1.0 · **Status:** proven end-to-end 2026-07-04 (triple-vendor) · **Owner:** Overmind/methods
> **Change log:** v1.0 — first codification, from the transport-NMA triple-vendor run.

## Purpose
Obtain a **genuine independent witness** of a headline result from a *different vendor's* model — not a
same-vendor re-run (that is reproducibility, not confirmation). Decorrelates from our Claude-heavy judge
panel; grounded in family-decorrelation ([[src-trinity]], `enforce_distinct_families`).

## When to use
Before promoting/shipping any quantitative headline (a pooled effect, a "beats X" claim, a manuscript
number). The maker (Claude) proposes; a **different vendor checks** before ship.

## Procedure
1. **Preflight auth** (fail loud, don't fake). Probe each vendor for *live* auth before assembling the
   quorum — see [[Codex-agy-Auth-Recipe-SOP]]. A smoke test that runs real code (`python -c "print(6*7)"`
   → `42`) proves execution, not just a login. If a seat is 401/revoked, emit `AUTH_DEGRADED` and record
   the witness as **NOT obtained** — never substitute a same-vendor re-run and call it cross-vendor.
2. **Dispatch identical, self-contained prompts** to each vendor (save them, e.g. `seatA_prompt.txt`), each
   re-deriving the result **from code/data**, not from our numbers.
3. **Each vendor writes its own raw artifact** (`verification/<vendor>_jobN_raw.md`).
4. **Re-check every number against the banked baseline** to the precision it was claimed at. Full double
   precision where available (today: `0.1575949114447188` matched exactly across Claude/agy).
5. **Adjudicate divergences explicitly** — tag NEW / OVERLAP / DIVERGENCE; when a vendor over-states, flag
   it (don't launder it into agreement). Record the *one* nuance if the panel converges on it (today: the
   HC one-cell WINS behind Codex's `REPRODUCED: PARTIAL`).
6. **Verdict line + did-any-headline-move.** Record `vendor=…, verdict=…, moved=Y/N`.

## Objective gate (what "witnessed" means)
Direction **and** magnitude reproduce under an independent vendor to the claimed precision, with all
divergences adjudicated. Absence of a cross-vendor check is a WARN on the ship verdict
(`OVERMIND_REQUIRE_CROSS_VENDOR_CHECK`, default record-only for the first cycle).

## Stop conditions
- **Success:** ≥1 different-vendor witness CONFIRMs to precision; nuances adjudicated. (Two = stronger; today
  we got Claude+Codex+agy.)
- **Failure:** no reachable different vendor (record NOT obtained + the unblock steps), or an unresolved
  DIVERGENCE that changes a headline → **tie-break needed**, do not ship. *(Live example: Codex WAVE-2
  refuted both wave-1 Claude P0s — tie-break still open; see [[P0-P1-Bug-Fixes]].)*

## Truth-first rules
- Reproducibility ≠ validity (both vendors recomputing the same possibly-flawed CSV can agree and both be
  wrong — see the κ NCT-duplication note in [[Triple-Vendor-Transport-NMA-Witness]]).
- Every borrowed number is re-checked, not trusted; over-statements are flagged, not smoothed.

## Ties to
[[Triple-Vendor-Transport-NMA-Witness]] · [[src-loop-library]] (multi-LLM convergence / Clodex loops) ·
[[Codex-agy-Auth-Recipe-SOP]] · [[_SOPs-MOC]].
