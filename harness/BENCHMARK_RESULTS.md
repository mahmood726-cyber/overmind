# BENCHMARK_RESULTS — the proof, run log (§3)

**Date:** 2026-07-04
**Harness:** `overmind/benchmark/` (arms A/B/C, deterministic witnesses, blinded held-out split,
checkpoint/resume, cost instrument). **Runner:** `scripts/run_benchmark.py` (capacity-aware,
re-runnable, resumes via checkpoint). **Slice:** `benchmark_data/` (64 tasks from 16 metafor-reproduced
gold fixtures; held-out = 35). **Scorecard:** `benchmark_data/runs/scorecard.{md,json}`.

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

| arm | status | caught-defect | false-alarm | parity | agreement | blended |
|---|---|---|---|---|---|---|
| **objective-ref** (witness-only floor, no model) | RUN | **0.654** (17/26) | **0.000** | **1.000** | 0.500 | 1.154 |
| **C-shadow** (stub reviewers + floor, plumbing proof) | SHADOW | 1.000 | 0.000 | 1.000 | 1.000 | 1.500 |
| A / B / C (model arms) | STAGED | — | — | — | — | — |

**Per-kind (objective reference, held-out):** impossible_cell **10/10**, reproduction **7/7**,
clean **9/9** (zero false alarms), direction **0/9**.

### What these numbers actually say (truth-first)
- The **deterministic objective floor is real and strong where a witness exists**: it catches every
  impossible-cell and reproduction defect with **zero false alarms** (parity 1.0). This is a genuine,
  reproducible baseline — the floor beneath Arm C.
- **It structurally misses reviewer-only defects**: direction 0/9, dragging caught-defect to 0.654 and
  agreement-soundness to 0.50 (it "accepts" the 9 direction defects it can't see). **This gap is the
  whole point** — it is exactly what the cross-vendor *reviewer* panel must close, and it is why a
  truth-gated harness is floor **+** panel, not floor alone.
- The **C-shadow** run (stub reviewers that flag the defects, on top of the floor) closes that gap:
  caught 0.654 → **1.000**, agreement 0.50 → **1.000**. This proves the Arm C plumbing
  (consensus-or-flag + objective-gate floor + checkpoint + scoring) works end-to-end. It is **not** a
  model result (stub reviewers) — it is a plumbing proof, labelled SHADOW.

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

## Honest limitations
- **Slice size (35 held-out)** is small — like MADE's ~24-task dev set, it can only surface failure
  modes present in these tasks. Expand fixtures before treating a result as decisive.
- **Defects are planted mechanically** (impossible cell = corrupt study 1; wrong estimate = ×1.8;
  wrong direction = flipped conclusion). They are representative, not exhaustive.
- **Reviewer-only coverage is one kind** (`direction`). Add more witness-blind defect types (bad
  subgroup, wrong model choice) to stress the panel harder.
- **C's floor advantage on witness-detectable defects is real but expected** — the honest question the
  staged run answers is whether the *heterogeneous reviewer panel* (C) beats a *single agent* (A) and a
  *homogeneous panel* (B) on the reviewer-only defects and at acceptable cost. That comparison needs the
  model arms, which are staged.
