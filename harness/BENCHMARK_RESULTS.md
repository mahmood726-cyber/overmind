# BENCHMARK_RESULTS — the proof, run log (§3)

## Laptop-node Claude probe + fleet re-check — 2026-07-06 09:38 (both nodes down; no valid panel)

Plan: re-probe pc1 headless Claude; if down, try the **laptop** (mahmo@100.80.183.43 over
Tailscale, key `node2_ed25519`) which was believed to hold a working Claude Code
subscription login; put whichever works into the decisive A/B/C. **Result: neither node
has a working headless Claude, and the fleet can't form a valid heterogeneous panel right
now.** Real smokes:

| node | headless `claude -p` | credential state |
|---|---|---|
| **pc1** | "Not logged in / run /login" | `.credentials.json` empty (len 0); env token stale 26-char |
| **laptop** | **401 Invalid authentication credentials** (confirmed even with env token cleared) | `.credentials.json` has a real **108-char accessToken but EXPIRED ~8 days ago**, **refreshToken len 0** (no auto-renew), subscriptionType `max`; env token also stale 26-char |

The laptop is *closer* (a real token, just lapsed) but **cannot self-refresh headlessly**
(no refresh token) → needs an interactive `claude` `/login` there. pc1 needs
`claude setup-token`. Per the "STOP if neither node works" rule, no Claude arm was run.

**Fleet re-probe at 09:38 (past the expected 08:57 codex reset):** codex did **NOT**
recover — both seats `exit 1: codex_models_manager::manager: fail` (persistent, consistent
with a balance cap not a weekly reset); **only agy live** (single family, historically
degraded ~45%). Since **Arm C requires ≥2 distinct live families**, a Claude-less
codex+agy decisive run is also impossible today — only agy is up. No arm was re-run
(would reproduce INVALID and burn agy quota for no new signal).

**Decision:** STOP, report honestly. **Decisive A/B/C remains NOT_PROVEN**, now blocked on
*two* fronts (Claude auth on both nodes; codex down; agy alone can't make C). Fastest real
unblock: an **interactive Claude `/login` on the laptop** (its token merely expired) — then
the SSH-worker route (harness on pc1 → `ssh laptop claude -p`) becomes viable; or
`claude setup-token` on pc1. No fabrication; no fallback wired (no working path to
smoke-prove).

## Headless-Claude auth-path investigation — 2026-07-06 (exhaustive; no non-stale path found)

Goal: unblock the Claude arm **without** an interactive token re-mint, on the hypothesis
that Claude authenticates via a different invocation than the harness's headless
`claude -p`. **Result: no such path exists on this node.** Every non-interactive Claude
credential path was tested and ruled out (real smokes, not assumptions):

| path tested | result |
|---|---|
| env `CLAUDE_CODE_OAUTH_TOKEN` (node Machine scope) | stale 26-char value → 401 (was already known) |
| `~/.claude/.credentials.json` `claudeAiOauth` | **empty** — accessToken len 0, refreshToken len 0, expiresAt 0 (subscriptionType `max`); CLI reports "Not logged in" |
| `claude -p` (`.local/bin`, v2.1.195) full inherited env | "Not logged in / run /login" (rc 1) |
| **desktop-bundled `claude.exe`** (`CLAUDE_CODE_EXECPATH`, v2.1.197, the exact binary this session uses) as a subprocess, full env incl. `CLAUDE_CODE_SDK_HAS_HOST_AUTH_REFRESH=1` | "Not logged in" (rc 1) |
| direct POST to `ANTHROPIC_BASE_URL/v1/messages`, no client bearer | **401** `{"type":"authentication_error","message":"x-api-key header is required"}` |
| `ANTHROPIC_API_KEY` | not set (Machine/User/process) |

**Root cause (confirmed, not guessed):** the auth that powers *this* Dispatch/code-task
session is held **in-process by the Claude desktop host** and served to the child it
launches over an **IPC channel** (host OAuth refresh). It is never persisted to a file,
env var, or the gateway as a reusable credential — `.credentials.json` is wiped to len-0,
and the base-URL gateway still demands `x-api-key`. A bare subprocess (the harness's
`claude -p` worker, or even a shell child of this authenticated session) inherits the
`*_HAS_OAUTH_REFRESH` *flags* but **not the IPC channel**, so it cannot obtain a token.
This is why the same session that answers here cannot hand its auth to `claude -p`.

**Decision (per the "don't fake it" rule):** no fallback adapter was wired — there is no
working path to smoke-prove, so wiring one would ship an unproven success path. The
harness's headless Claude genuinely requires a fresh credential:
`claude setup-token` + `setx CLAUDE_CODE_OAUTH_TOKEN <token>` (interactive TTY), **or** an
interactive `claude` `/login` to repopulate `.credentials.json`. **A/B/C was NOT re-run:**
no vendor state changed (Claude still down, codex capped until ~08:57 reset, agy degraded),
so a re-run would reproduce the same INVALID B/C. Re-run when Claude is re-minted (metered
→ first real cost-per-accepted) and/or after the codex reset.

## Live A/B/C run — 2026-07-05 ~23:00–23:40 local (FIRST VALID MODEL ARM; verdict NOT_PROVEN)

Ran `scripts/run_benchmark.py --max-tasks=40` (released, checkpoint/resumable) on a
deterministic **40-task SUBSET of the sealed held-out slice** (frozen slice untouched):
**35 defects (15 witness-detectable + 20 reviewer-only) + 5 clean.** Real exec-smoke
preflight (not `login status`).

**Vendor reality this run:** codex:mahmood **LIVE** (~14 s/call); agy **LIVE** but
**degraded** (~20 s/call, 45% usable); codex:noreen DOWN (exit 1); claude:oauth DOWN
(stale 26-char token); gemini:api DOWN (HTTP 429). Effective sustained capacity ≈ **1.4
vendors**.

**What actually ran per arm:**
- **Arm A — single codex: VALID (39/40 usable, 98%).** This is the **first valid live
  model arm** the benchmark has produced.
- **Arm B — codex ×3: INVALID (5% usable).** codex **capped at the A→B boundary**
  (`exit 1: codex_models_manager` + `TimeoutExpired`); Arm A had consumed codex's ~40-call
  weekly headroom. Correctly auto-flagged INVALID by `runner.MIN_USABLE_RATE`.
- **Arm C — codex + agy + witness floor: INVALID (22% usable).** codex 0/40 (fully
  capped), agy 18/40 (45%, empty-text / driver-envelope artifacts). Correctly INVALID.

| arm | status | caught | false-alarm | parity | agreement | blended |
|---|---|---|---|---|---|---|
| **A — single codex** | **RUN (VALID)** | **0.629** (22/35) | **0.400** (2/5) | 1.000 | 0.188 | 0.729 |
| B — codex ×3 | INVALID (usable 5%) | *0.029* | *0.000* | — | *0.128* | — |
| C — codex+agy+floor | INVALID (usable 22%) | *0.657* | *0.200* | *1.000* | *0.250* | — |
| objective-ref (floor, no model) | RUN | 0.429 (15/35) | 0.000 | 1.000 | 0.200 | 0.929 |
| C-shadow (stub reviewers) | SHADOW | 1.000 | 0.000 | 1.000 | 1.000 | 1.500 |
| objective-ref [FROZEN, sealed] | FROZEN | 0.292 | 0.000 | 1.000 | 0.019 | 0.792 |

*Italic B/C figures are backend artifacts of a degraded fleet — **NOT scored as real**.
C's 0.657 is NOT "beating A": 62/80 reviews failed; it is dominated by the deterministic
floor + a few agy reviews, not a valid panel.*

**Wilson 95% CI (the one valid arm, A):** caught 0.629 → **[0.463, 0.768]**; false-alarm
0.400 → **[0.118, 0.769]** (5 clean tasks — wide, honest).

**Findings on the valid arm (single codex):** caught **14/15 witness-detectable** but
only **8/20 reviewer-only**, at **FAR 0.40**. Two concrete honesties: (a) it **missed a
witness-detectable `ci_invalid`** that the deterministic floor catches — evidence for
keeping the witness floor *under* the reviewers in C; (b) both false alarms were on
**all-zero-event** clean tasks (codex flagged "RR not estimable") — defensible skepticism
scored as crying wolf, precisely the cost the C consensus gate is meant to suppress. The
floor alone catches **0/20** reviewer-only; a single agent recovers **8/20** but pays
FAR 0.0→0.40. **Whether C recovers those catches without the FAR penalty is the untested
question.**

**Cost / economics — NOT_PROVEN in dollars.** codex/agy are subscription seats → the cost
instrument reads **$0 marginal** on every arm; real $/accepted needs the **metered Claude
lane** (down). Binding cost is the **codex weekly cap** (exhausted after ~40 calls).

**Did Arm C beat A and B? NO — NOT_PROVEN.** The differentiator never earned a valid
measurement (fleet degraded mid-run). We do not claim a win, and the machinery did not
manufacture one: the usable-rate guard flagged B/C INVALID and `evaluate_win_condition`
returned pending. **Two-slice promotion N/A** — no valid held-out C delta to promote.

**Unblock (in order):** (1) fresh Claude OAuth token on the node — not capped, **metered**,
unblocks Arm A + first real $/accepted; (2) codex weekly refill; (3) agy throttle clearing
to ≥50% sustained. `benchmark_autostage.py` resumes via checkpoint on capacity return.
Artifacts: `benchmark_data/runs_live/scorecard.{md,json}` + `arm_{A,B,C}.jsonl`.

---

**Date:** 2026-07-04
**Harness:** `overmind/benchmark/` (arms A/B/C, deterministic witnesses, blinded held-out split,
checkpoint/resume, cost instrument). **Runner:** `scripts/run_benchmark.py` (capacity-aware,
re-runnable, resumes via checkpoint). **Slice:** `benchmark_data/` (330 tasks from 33 metafor-reproduced
gold fixtures × 10 kinds; held-out = 139 (frozen split carved out 73)). **Scorecard:** `benchmark_data/runs/scorecard.{md,json}`.

## Live-capacity run — 2026-07-05 (agy passed the smoke but is degraded under load)
Fresh real preflight: **agy LIVE** (smoke "ok"), Codex both seats DOWN (`exit 1`, refill not through),
Claude stale-token, Gemini not retested. Ran **Arm A (agy)** + started **Arm B (agy×3)** on a 20-task
held-out subset (agy ~35 s/call). **Result: INVALID — agy is intermittently degraded.** Over 20 Arm-A
tasks agy produced a **real review on only 4 (20% usable-rate)**: 3 hard `JUDGE_ERROR: empty text` + 13
driver-envelope responses (`Created At…Completed At…`, no `FLAG:` line). Only the obvious impossible-cell
cases got genuine reviews (agy correctly caught "128 events > N of 12").

**Truth-first decision:** 80% of the verdicts are backend artifacts (empty → parsed `flag=False`), **not
agy's judgment** — so **no valid Arm A/B was produced** (fabricating one from a throttled backend would
be dishonest). The single preflight smoke passed because one call succeeded; sustained throughput is
degraded. Run stopped.

**This exposed a real harness gap → fixed (additive, tested):** a reviewer response with no parseable
`FLAG:` (empty / envelope / `JUDGE_ERROR`) is now marked **`usable=False`** (`reviewers.py`), the runner
tracks a per-arm **usable-rate**, and an arm below **50%** usable is reported **INVALID (vendor
degraded)** rather than silently scored as a rubber-stamp (`runner.MIN_USABLE_RATE`). The agy run is
correctly detected INVALID at 20%. So a future degraded-vendor run can never masquerade as a real arm.

**Verdict: still pending / NOT_PROVEN.** No vendor currently sustains a valid arm (agy degraded, Codex
capped, Claude stale-token). `benchmark_autostage.py` retries on capacity; the fastest clean unblock is a
fresh Claude token (`claude setup-token` + `setx` — Claude is metered, so it would also give real
cost-per-accepted numbers).

## Live-capacity run — 2026-07-04 (attempted NOW, not waiting for 00:35Z)
Auth-preflighted every vendor with a **real smoke** (not login-status). **Verified state — no vendor
produces a real completion right now:**
| vendor | real-smoke result |
|---|---|
| **agy** | daemon up but returns **empty text** (`"text": ""`) on 3 attempts (pro/flash/pro) — throttled/down, NOT live |
| **codex** (both seats) | `exit 1` (credit-capped; model field empty) |
| **claude** (oauth) | stale node token → no auth (401) |
| **gemini** (api) | HTTP 429 Too Many Requests |

**Truth-first decision:** agy returning empty text ≠ a live agent — routed through a reviewer it would
make every verdict `flag=False` (a degenerate rubber-stamp), which is an empty-backend artifact, **not
agy's judgment**. So **no real-model Arm A/B/C was run** — fabricating one would be dishonest. The
harness executed correctly: preflight → no live vendors → deterministic **objective floor + C-shadow on
the FROZEN-protected held-out slice** → **Arms A/B/C STAGED**; the win-condition evaluator correctly
returns **pending/NOT_PROVEN** (C not live). Scorecard records every per-vendor DOWN reason.

**n_eff behaviour Arm B (agy×3) would expose — demonstrated mechanically (AN-3, no model needed):**
| panel | n_eff | families | consensus? |
|---|---|---|---|
| **Arm B: agy ×3 (homogeneous)** | **1.2** | 1 | **NO → fall through to the D2 witness** |
| Arm C: agy + codex + claude | 3.0 | 3 | yes → consensus |
| Arm C-min: agy + codex | 2.0 | 2 | yes → consensus |
The decorrelation gate correctly refuses to treat 3× same-vendor agreement as consensus — the exact
failure Arm B is designed to expose, verified without a live model.

**Still pending for the full A/B/C verdict:** **any ONE** live frontier vendor unblocks a real **Arm A**
(and Arm B ×3); **Arm C** needs **≥2 distinct live families**. Nearest unblocks: Codex credit refill
(~00:19Z), a fresh Claude subscription token (`claude setup-token` + `setx`, unblocks immediately —
Claude is not capped), or agy throttle clearing. `scripts/benchmark_autostage.py` fires them on capacity
return, resuming via checkpoint. The **C-shadow** reference (caught 1.000, agreement 1.000) already
stands as the plumbing proof.

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

**Expanded slice + frozen split (2026-07-04, decisive; current numbers):** **330 tasks** from **33**
metafor-reproduced 2×2 gold fixtures × **10 kinds**, three-way split (AN-2): **dev=118 / held-out=139 /
FROZEN=73**. Held-out this run: **126 defect, 13 clean, 83 reviewer-only**.

| arm | status | caught-defect | false-alarm | parity | agreement | blended |
|---|---|---|---|---|---|---|
| **objective-ref** (witness-only floor, no model), held-out | RUN | **0.341** (43/126) | **0.000** | **1.000** | **0.135** | 0.841 |
| **objective-ref [FROZEN slice, sealed]** | FROZEN | 0.292 | 0.000 | 1.000 | 0.019 | 0.792 |
| **C-shadow** (stub reviewers + floor, plumbing proof) | SHADOW | 1.000 | 0.000 | 1.000 | 1.000 | 1.500 |
| A / B / C (model arms) | STAGED | — | — | — | — | — |

**Per-class (objective reference, held-out):** witness-detectable **43/43** (impossible_cell +
reproduction + ci_invalid, perfect), clean **13/13** (zero false alarms), **reviewer-only 0/83**
(all six classes — the floor structurally cannot see them).

### What these numbers actually say (truth-first)
- The **floor is 0.341** on the frozen-protected held-out slice (0.292 on the sealed frozen slice) —
  far below the old 35-task slice's 0.654, which is **honest, not a regression**: the expanded slice is
  dominated by *reviewer-only* defects (83 of 126) the deterministic floor cannot catch.
- Where a witness exists the floor is still **perfect (43/43) with zero false alarms** (parity 1.0).
- **The reviewer-only gap the panel must close is 83 held-out tasks (was 9)** across six realistic
  classes — a large, decisive target. Agreement-soundness **0.135** shows the cost of floor-alone: it
  "accepts" 83 defects it can't see.
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

## Foundational benchmark reference + cross-check — "AI Agents That Matter" (arXiv:2407.01502)
**Kapoor, Stroebl, Siegel, Nadgir & Narayanan (2024)** is the authoritative reference for our benchmark
design (verified via the paper + HTML). It prescribes exactly our discipline; the cross-check below asks
whether any of its concrete prescriptions we do **not** already implement.

| Their prescription (concrete) | Us | Status |
|---|---|---|
| **Jointly optimize cost + accuracy**; report agents on a **cost–accuracy Pareto frontier** ("the cost of running these agents isn't a top-line metric reported") | cost-per-accepted-change (D5) in the blended score + the affordability gate in the win condition | **already covered** (cost is first-class); a literal Pareto-frontier *plot* is a future viz — noted |
| **Adequate holdout, withheld at the right generality level; keep it secret** ("agents take shortcuts and overfit") | two-slice **frozen** rule (AN-2) + sha256 held-out + answer keys off the agent surface | **already covered**, and we go further (frozen slice never scored during evolution) |
| **Enumerate shortcut types** (distribution/task/domain/general; hardcoded policies) | BenchJack audit (AN-7) probes id-leak / keyword-shortcut / template-uniformity | **already covered** |
| **Standardization / reproducibility: release the eval script, be order-invariant** | `scripts/run_benchmark.py` released + deterministic; checkpoint/resume ⇒ order-invariant | **already covered** |
| **Report error bars** ("agent evaluations are rarely accompanied by error bars") | point estimates only, previously | **ADOPTED — delta 1** |
| **Withhold at generality level = whole tasks, not just samples** | we withhold task *variants* by id, but the same source *fixture* spans dev + held-out | **ADOPTED — delta 2 (disclosure)** |

**Adopt-delta 1 — Wilson 95% CIs (`scoring.wilson_ci`).** Every rate metric (caught-defect, false-alarm)
now carries a Wilson score 95% CI in the scorecard — honest error bars, especially on the smaller
agy-latency-bounded live runs. (Wilson, not normal-approx, for good behaviour at small n / near 0-1.)

**Adopt-delta 2 — fixture-level holdout disclosure (`tasks.fixture_leakage`).** Their "withhold at the
right generality level" exposes a real gap: our split holds out task *variants*, but on the current
corpus **all 33 held-out fixtures share a source fixture with dev** (frozen: 29/33). So an agent could
learn a fixture's true pooled estimate from a dev variant and apply it to a held-out variant. This is now
**measured and disclosed** (`fixture_of` + `fixture_leakage`); a strictly-more-rigorous **fixture-level
split** (no shared source fixture across slices) is recorded as the next hardening step.

**Net cross-check result:** **aligned on 4 of 6; adopted 2 deltas** (Wilson CIs; fixture-leakage
disclosure). No prescription was found that is both un-covered and un-addressed.

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
