# SOP — Single-Writer Rule

> **Version:** v1.0 · **Status:** active convention · **Owner:** all repos
> **Change log:** v1.0 — codified 2026-07-04 from the P0/P1 fix discipline + memory (single-writer store).

## Purpose
Prevent silent corruption and dual-source-of-truth drift: **one writer owns each artifact / state class**;
everyone else mirrors or reads. Truth-first re-derivation of every number a fix touches.

## The rule
1. **One authoritative writer per artifact.** For a given state class (a `STUCK_FAILURES.jsonl`, a
   `.progress_<date>.json`, a manuscript number, a frozen deploy CSV) exactly one process/loop writes it;
   others **mirror additively** and read. When mirroring into a machine store (MemClaw, [[src-memclaw]]),
   the **file state stays the single source of truth** and the mirror is a floor/audit copy — never
   dual-source the same fact.
2. **Truth-first re-derivation.** When a fix changes code that produced a committed number, **re-derive and
   re-commit every affected number** at the precision it was reported (today: Copas aspirin −0.074→−0.085
   propagated to `manuscript.md`, `build_jats.py`, `build_pdf.py`; k-fold MAE regenerated in
   `benchmark_learned_results.json`). A fix that leaves stale downstream numbers is not done.
3. **Flag, don't silently change, out-of-scope siblings.** If a fix reveals a sibling now inconsistent
   (e.g. `single-arm-proportion.js` still DL after the forest went PM), **flag it for a follow-up sync** —
   do not expand scope and silently edit it.
4. **Frozen/deploy paths are write-once.** The frozen κ (`aact_kappa_freeze.py`) is the deployed value;
   defects found in the *upstream* diagnostic (`aact_kappa.py`) do not retroactively rewrite the freeze —
   they are logged and adjudicated separately.

## Why (past incidents)
Field-name contract drift silently corrupted 465 reviews once; registry drift disagreed by 45+ projects.
Single-writer + re-derivation is the counter-discipline. Concurrent writers to the same artifact = the
class of bug this exists to kill (cf. durable-execution "two processes resume the same thread_id").

## Objective gate
No committed number contradicts the code that produced it (re-run reproduces it); no artifact has two live
writers; every out-of-scope inconsistency is flagged, not silently patched.

## Stop conditions
- **Success:** all affected numbers re-derived + committed; siblings flagged; mirror ≠ source confirmed.
- **Failure:** a number can't be re-derived (missing baseline) → that is **not** a release pass; log the
  blocker (`STUCK_FAILURES`), do not promote.

## Ties to
[[P0-P1-Bug-Fixes]] · [[src-memclaw]] (machine mirror, file = floor) · [[Gated-Additive-Deploy-SOP]] ·
[[_SOPs-MOC]].
