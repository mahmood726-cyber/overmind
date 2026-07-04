# BENCHMARK_RESULTS — the proof, run log (§3)

**Date:** 2026-07-04
**Harness:** `overmind/benchmark/` (arms A/B/C, deterministic witnesses, blinded held-out split,
checkpoint/resume, cost instrument). **Runner:** `scripts/run_benchmark.py` (capacity-aware,
re-runnable, resumes via checkpoint). **Slice:** `benchmark_data/` (330 tasks from 33 metafor-reproduced
gold fixtures × 10 kinds; held-out = 164). **Scorecard:** `benchmark_data/runs/scorecard.{md,json}`.

## What ran this session (real, reproducible)

**Capacity reality (updated after the OAuth fix):** headless Claude does **not** need an API key — it
runs `claude -p` on the **subscription** via `CLAUDE_CODE_OAUTH_TOKEN` (OAuth bearer). The earlier "not
logged in" was a bug: `safe_subprocess_env()` **stripped** the token (never allowlisted), so the
subprocess never received it. **Fixed** (commit `a735d73`): the token is now allowlisted + passed as a
bearer, and headless Claude is a **first-class, non-capped vendor** in the preflight.

**But the node's persisted token is STALE** — `CLAUDE_CODE_OAUTH_TOKEN` (Machine scope) is a malformed
26-char value (`sk-ant-oat-P…`) returning **HTTP 401 Invalid bearer token**. The mechanism is proven
(with a token set, `claude -p` uses bearer auth, reports `total_cost_usd`, no API key); the *only*
blocker is token validity, and a fresh token can't be minted headlessly (`claude setup-token` needs an
interactive TTY). **One-line node fix (interactive, on the node):**
```
claude setup-token                               # OAuth flow -> long-lived token
setx CLAUDE_CODE_OAUTH_TOKEN "sk-ant-oat01-…"    # replaces the stale 26-char value
```
Then `scripts/benchmark_autostage.py` runs Arm A (+ Arm C's Claude reviewer) live — Claude is not
capped, so it does not wait for the ~5h refill. This session: Codex credit-capped, Gemini 429, Claude
token stale → no model arm ran; the real numbers below are the deterministic floor, model arms **staged**.

**Expanded slice (2026-07-04, decisive):** **330 tasks** from **33** metafor-reproduced 2×2 gold
fixtures × **10 kinds**; **held-out = 164** (146 defect, 18 clean; **101 reviewer-only** defects).

| arm | status | caught-defect | false-alarm | parity | agreement | blended |
|---|---|---|---|---|---|---|
| **objective-ref** (witness-only floor, no model) | RUN | **0.308** (45/146) | **0.000** | **1.000** | **0.151** | 0.808 |
| **C-shadow** (stub reviewers + floor, plumbing proof) | SHADOW | 1.000 | 0.000 | 1.000 | 1.000 | 1.500 |
| A / B / C (model arms) | STAGED | — | — | — | — | — |

**Per-class (objective reference, held-out):** witness-detectable **45/45** (impossible_cell +
reproduction + ci_invalid, perfect), clean **18/18** (zero false alarms), **reviewer-only 0/101**
(all six classes — the floor structurally cannot see them).

### What these numbers actually say (truth-first)
- The **floor dropped from 0.654 (old 35-task slice) to 0.308** — this is **honest, not a regression**:
  the expanded slice is dominated by *reviewer-only* defects (101 of 146), which the deterministic floor
  cannot catch. A bigger, more realistic slice **lowered** the floor's caught-rate, exactly as expected.
- Where a witness exists the floor is still **perfect (45/45) with zero false alarms** (parity 1.0).
- **The reviewer-only gap the panel must close is now 101 held-out tasks (was 9)** across six realistic
  classes — a large, decisive target, not a small-sample artifact. Agreement-soundness **0.151** shows
  the cost of floor-alone: it "accepts" 101 defects it can't see.
- **C-shadow** (stub reviewers flagging defects, on the floor) closes the whole gap: caught 0.308 →
  **1.000**, agreement 0.151 → **1.000** — proving the Arm C plumbing works end-to-end. It is a
  plumbing proof (stub reviewers), not a model result; labelled SHADOW.

### Defect classes (10 kinds/fixture; sealed answer key each)
**Witness-detectable** (deterministic battery fires): `impossible_cell` (events>N), `reproduction`
(pooled estimate ≠ data), `ci_invalid` (transposed CI, lo>hi).
**Reviewer-only** (data passes every deterministic check; defect in the narrative — mirrors real errors
we hit): `direction` (conclusion contradicts data), `wrong_measure_label` (ratio data described as a
continuous MD outcome — the **MD→"RR" mislabel**), `method_mismatch` (naive pool despite funnel
asymmetry — the **Copas naive-pool**), `comparator_swap` (arms swapped in the narrative — the **pubHR
comparator mismatch**), `missing_reference` (claims historical borrowing but no reference/null arm — the
**RM-BRIDGE missing null**), `subgroup_mismatch` (analysis label ≠ outcome described).
A verified integrity property (`test_witness_integrity_fires_only_on_witness_detectable`): the
kind-agnostic witness battery fires on **exactly** the witness-detectable kinds and **never** on a
reviewer-only or clean task — so the reviewer-only defects are genuinely witness-proof.

## Staged: Arms A, B, C on capacity return (~21:00, auto-resume)

The model arms run the moment vendors are live, via **`scripts/benchmark_autostage.py`** (idempotent):
1. it reads the reliability **cap-log**; if Codex/agy/Gemini seats are still capped it prints the
   `reset_at` and exits (nothing to do);
2. once caps clear it runs `scripts/run_benchmark.py`, which **auth-preflights** each vendor (real exec
   smoke, not `login status`) and runs whatever is live, **resuming completed tasks via checkpoint**.

- **A — single frontier model** (Claude when its subprocess is authed; else any one live frontier).
- **B — homogeneous panel** (same vendor ×3) — isolates "more agents ≠ vendor diversity".
- **C — heterogeneous panel** across ≥2 distinct live families (Claude / Codex / agy|Gemini) **+ the
  objective floor**.

The supervised drain loop already models the ~5h credit refill (`SupervisedLoop`, `CREDIT_REFILL_SECONDS`)
and auto-resumes; wiring `benchmark_autostage.py` into its post-recovery hook (or a schedule near the
refill) makes A/B/C fire without a session staying awake.

## The win condition (can report NOT winning)
`scoring.evaluate_win_condition` returns **WORLD_CLASS** only if, on held-out:
1. C > A on caught-defect **and** agreement, false-alarm no worse; **and**
2. C > B on caught-defect **or** agreement at ≤ cost-per-accepted (diversity pays); **and**
3. C's cost-per-accepted ≤ K× A's (affordable).
Otherwise **NOT_PROVEN**, with explicit notes (B≈C → heterogeneity not paying; cost≫A → unaffordable;
high false-alarm → crying wolf). Weights + K are pinned before the run; the held-out answer keys are
read only by the scorer (blinding). **The benchmark is built to be able to show us not winning.**

## Reproducibility + blinding note
The sealed answer keys (`benchmark_data/keys/`) are **deliberately not committed** — the `keys/` path
is gitignored (secret-protection convention), which doubles as **blinding**: keys stay off the repo
surface. Regenerate the full slice (tasks + keys) deterministically from the committed gold corpus:
```bash
python -c "from overmind.benchmark.generate import write_slice; print(write_slice('benchmark_data'))"
```
`tasks.json` (artifacts) and the scorecard are committed as the run record; the generator is
deterministic, so keys reproduce identically.

## Limitations — addressed vs still open (updated 2026-07-04)
**Addressed this session (slice-hardening):**
- ✅ **Slice size** — grown **35 → 164 held-out** (330 total, 33 fixtures × 10 kinds), keeping the
  deterministic sha256 held-out split. No longer small-sample.
- ✅ **Reviewer-only coverage** — expanded from one class (`direction`) to **six** (direction,
  wrong_measure_label, method_mismatch, comparator_swap, missing_reference, subgroup_mismatch) →
  **101 reviewer-only held-out tasks**, the decisive target for the panel.
- ✅ **Mechanical artificiality reduced** — five reviewer-only classes mirror **real errors we hit**
  (MD→"RR" mislabel, Copas naive-pool, pubHR comparator mismatch, RM-BRIDGE missing null, analysis
  mismatch), so the benchmark measures detection of realistic error classes, not only toy corruptions.
- ✅ **Witness integrity verified** — the kind-agnostic battery fires on exactly the witness-detectable
  kinds and never on reviewer-only/clean (unit-tested), so reviewer-only defects are genuinely
  witness-proof and the floor's blind spot is real, not an artifact.

**Still open:**
- **Fixture domain** — all fixtures are 2×2 count data (RR/OR). Continuous (MD/SMD), survival (HR), DTA,
  and NMA fixtures would broaden coverage; the `wrong_measure_label` class gestures at this but the
  underlying data are still counts.
- **Reviewer-only defects are still narrative-templated** (one template per class per fixture). Realistic
  but not adversarially diverse; paraphrase/vary templates to prevent a reviewer from pattern-matching
  the wording rather than the substance.
- **Some reviewer-only classes carry a judgment component** (`method_mismatch`, `subgroup_mismatch`):
  ground truth is defensible but not as crisp as an arithmetic defect. Kept, flagged.
- **The decisive question still needs the model arms** — whether the *heterogeneous panel* (C) beats a
  *single agent* (A) and a *homogeneous panel* (B) on the 101 reviewer-only defects at acceptable cost.
  A/B/C are staged; the expanded slice makes that verdict meaningful when they run.
