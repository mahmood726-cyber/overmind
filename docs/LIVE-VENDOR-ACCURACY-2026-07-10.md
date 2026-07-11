# Live-Vendor Accuracy 2026-07-10 — closing GAP #1

**Date:** 2026-07-10 · **measurement-only** (no harness behaviour changed; driver on a feature branch, held for go).
Closes the peer-benchmark's #1 open item: *the harness's evals were fixture-based; this is a real **live-vendor**
accuracy number* over a sealed, labelled corpus.

**Headline (verified-live, CLEAN two-healthy-vendor run):** on the sealed held-out slice (n=139, 126 defects),
the harness's real cross-vendor verification path — **Arm C (Codex + agy + objective floor)** — caught
**94.4% of defects, 119/126, Wilson-95% CI [89.0%, 97.3%]**, with **both vendors healthy** (Codex 100% usable,
agy 91%). The honest cost: a **false-alarm rate of 46.2% (6/13 cleans)** — high recall bought with high
false-alarm on the small clean set (the conformal gate did **not** reduce it this pass; see §5).

> **This number supersedes an earlier degraded figure.** The first full pass reported Arm C = 0.921 with the
> Codex lane at only 63% usable (a cp1252 UTF-8 stdin bug in the driver + the Codex seat briefly out of credits).
> The bug was fixed and the run **resumed** (re-executing only the 51 Codex-failed items, §2b); with a healthy
> Codex the number rose to **0.944**, confirming 0.921 was a lower bound. All figures below are the clean run.

---

## 1. Method (stated before running — the number is well-defined)

**Corpus — the sealed held-out slice of the MADE-style A/B/C benchmark** (`benchmark_data/tasks.json`,
deterministic sha256 split; not hand-picked). **n = 139**: **126 defects** + **13 clean**. The 126 defects split
into **43 witness-detectable** (a deterministic check fires: `impossible_cell`, `reproduction`, `ci_invalid`) and
**83 reviewer-only** (data passes every deterministic check; the defect is in the narrative: `direction`,
`wrong_measure_label`, `method_mismatch`, `comparator_swap`, `missing_reference`, `subgroup_mismatch`). **Labels
are pre-existing** (sealed `keys/keys.json`), **read only by the scorer** — the reviewer path never sees them
(blinding preserved). Nothing fabricated.

**Live heterogeneous panel** (both seats confirmed live by real exec first — `codex login status` lies):
- **Codex mahmood726** on the laptop over SSH (`mahmo@100.80.183.43`, key `node2_ed25519`), `codex exec
  --sandbox read-only --config model_reasoning_effort=medium -` — **family: openai**.
- **agy flash_lite** local (the harness's real `AgyBackend`, incl. its async-envelope directive+retry) —
  **family: google**.
- **deterministic objective witness** (`overmind/benchmark/witnesses.run_witness`) — the D2 floor.

**Arms scored** (the harness's own aggregation code — `overmind/benchmark/arms.py`):
- **objective-ref** — witness-only floor, no reviewers (deterministic; structurally can catch at most the 43
  witness-detectable defects).
- **A — single Codex** — one reviewer's flag (single-vendor baseline).
- **C — Codex + agy + floor** — heterogeneous consensus-or-flag with the objective floor (the harness's real
  verification path; the differentiator).
- **C (conformal gate)** — Arm C re-derived with the calibrated conformal accept/abstain gate (`alpha=0.10`,
  retain ≥90% of catches), the PV-B lever on the false-alarm clause.

**Metric — exactly the peer-doc gap** (`overmind/benchmark/scoring.score_arm`):
- **caught_defect_rate** = caught / 126 (recall over defects), with **Wilson 95% CI**.
- **false_alarm_rate** = false_alarms / 13 (FPR over cleans), with **Wilson 95% CI** (small clean denominator —
  the CI is wide; stated honestly).
- Reviewer usable-rate is tracked; an arm whose reviewers are unusable on >50% of tasks is reported **INVALID**
  (a degraded-vendor artifact, not a real measurement — `runner.MIN_USABLE_RATE`).

**What is and isn't ours in this number:** the accuracy is computed **entirely by the harness's own code**
(reviewer prompt+parser, arm aggregation, objective witness, Wilson-CI scorer, conformal gate). The only new code
is `SshCodexBackend` — a transport wrapper that runs the *same* `codex exec` the local backend runs, on the
laptop over SSH. Driver: `evals/live_vendor_accuracy.py` (feature branch, benchmark unit tests green:
130 passed / 8 skipped).

---

## 2. Results (live, held-out n=139; 126 defects / 13 clean)

**Vendor usable-rate (clean run):** Codex **139/139 = 100%**; agy **126/139 = 91%**. Both healthy — a genuine
two-frontier-vendor measurement.

**Decomposition (every row scored by the harness's own `score_arm`; a single live pass, no seed averaging):**

| arm | caught-defect | Wilson 95% CI | false-alarm (n=13) | what it isolates |
|---|:--:|:--:|:--:|---|
| **objective-ref** (witness-only floor, deterministic) | **0.341** | [0.264, 0.428] | 0.000 (0/13) | the deterministic base — catches exactly the 43 witness-detectable defects, structurally misses all 83 reviewer-only |
| Codex only | 0.706 | [0.622, 0.779] | 0.308 (4/13) | single frontier vendor alone |
| agy only | 0.841 | [0.768, 0.895] | 0.462 (6/13) | one reliable cheap reviewer alone |
| Codex + floor | 0.762 | [0.681, 0.828] | 0.308 (4/13) | frontier + deterministic floor |
| agy + floor | 0.881 | [0.813, 0.927] | 0.462 (6/13) | cheap reviewer + deterministic floor |
| **★ C = Codex + agy + floor** (the harness path) | **0.944** | **[0.890, 0.973]** | 0.462 (6/13) | **heterogeneous consensus-or-flag + floor — the differentiator** |
| C + conformal gate (α=0.10) | 0.944 | [0.890, 0.973] | 0.462 (6/13) | FAR-control lever — **abstained 0 this pass; did not reduce FAR** (see §5) |

**The differentiator holds cleanly:** C (0.944) beats **every** single lane — agy+floor (0.881, so heterogeneity
adds **+6.3pp**), agy-only (0.841), Codex+floor (0.762), Codex-only (0.706), and the deterministic floor alone
(0.341, +60pp from the reviewer panel). Both vendors contribute: neither alone reaches C, and the second,
different-family vendor closes real gaps the first misses.

### 2a. Reading the number honestly
- **Recall is strong and clean:** 0.944 [0.890, 0.973] on 126 blinded defects, both vendors healthy.
- **False-alarm is the genuine weakness:** 6 of 13 correct artifacts flagged (0.462). Consensus-or-flag
  (flag-on-any-dissent) unions the two vendors' false alarms, and agy over-flags cleans (agy-only FAR 0.462);
  13 cleans is a small denominator (wide CI [0.232, 0.709]). **This is the real gap to close**, not the recall.
- **The conformal FAR lever did not fire this pass** (0 abstentions) — the harness's reviewers emit no numeric
  confidence, so the gate had no sub-τ flags to abstain; FAR stayed 0.462. (In the earlier degraded pass the
  flag distribution happened to let it cut FAR to 0.308 — data-dependent, not reliable.) Making the conformal
  gate actually control FAR needs a per-flag confidence signal — a concrete follow-up.

### 2b. The degradation encountered, and the resume that resolved it
The first full pass had Codex at only 63% usable: **44 of 51 failures were a cp1252 UTF-8 stdin bug in the
driver** (`subprocess` mangled non-ASCII artifact chars — em-dash, ±, ≤ — so `codex exec` rejected the prompt as
"input is not valid UTF-8"; *my transport, not Codex or the harness* — I hit my own documented cp1252 trap), the
rest a brief Codex credit blip. Fixed the driver (send explicit UTF-8 bytes) and **resumed**: the runner
re-executes only tasks whose recorded Codex review was unusable, so the resume redid **51** items, not all 139,
lifting Codex to 100% usable and Arm C from 0.921 → **0.944**. The resume mechanism is documented in
**§6 (RERUN / RESUME)** for future credit outages.

---

## 3. Reading the number

- **objective-ref** is the deterministic floor: it catches witness-detectable defects but **structurally misses
  the 83 reviewer-only defects** — that gap is exactly what a cross-vendor reviewer panel must close.
- **Arm C − objective-ref** = what the **live cross-vendor reviewers add** on top of the deterministic floor.
- **Arm C vs Arm A** = the **heterogeneity contribution** (a second, different-family vendor catching what the
  first missed) — the core differentiator, now on live vendors rather than fixtures.
- **False-alarm rate** is over only 13 cleans, so its CI is wide; the **conformal gate** row is the FAR-control
  lever. Report both raw and gated.

## 4. Like-for-like comparison to peers (honest framing)

The nearest publicly-benchmarked peer is **ARA** (Agentic Reproducibility Assessment), which scores ~**61%** on
ReScience C / ReproBench / GoldStandardDB ([2605.02651](https://arxiv.org/html/2605.02651v1)). **Framing
mismatch, stated plainly:** ARA scores *document-level reconstructability from a paper's text* (can this be
reproduced?), a **different task** from ours (*given a computed artifact, is there a defect? flag-or-accept*).
The two numbers are **not directly comparable** — ARA is a graded reproducibility assessment, ours is
defect-detection recall/FPR on a blinded artifact set. What is comparable is the *shape*: both are held-out,
label-blinded, and report an accuracy against human/ground-truth labels. We report ours on our own task and do
**not** claim it beats ARA's on ARA's task.

## 5. Honest limits
- **False-alarm rate is the real weakness, not recall:** 46.2% (6/13 cleans wrongly flagged). Both vendors
  contribute false alarms and consensus-or-flag unions them; 13 cleans is a small denominator (wide CI). The
  conformal gate **did not reduce it this pass** (0 abstentions — the reviewers emit no per-flag confidence
  signal for the gate to threshold on). Closing FAR needs (a) a per-flag confidence, and (b) more clean cases.
- **Effort:** Codex at `reasoning_effort=medium` — conservative vs the harness default (xhigh), which would only
  help recall.
- **agy `flash_lite` alone caught 84.1%** — a cheap model reads reviewer-only defects well; the heterogeneity
  gain (agy+floor 0.881 → C 0.944, +6.3pp) is real but modest, i.e. one reliable vendor + floor already gets
  ~88%, and the second different-family vendor adds the last few points and closes specific blind spots.
- **Single live pass, no seed averaging** — vendor calls are mildly nondeterministic; a re-run lands a slightly
  different point within the CI. This is one clean pass, not a distribution.
- **Arm B (homogeneous ×3) not run live** — the live contrast here is single (A, 0.706) vs heterogeneous
  (C, 0.944); the B<A finding is from prior runs, not re-measured here.

---

## 6. RERUN / RESUME WHEN CODEX CREDITS RETURN

The driver is a **genuine one-command resume**. A task is re-executed iff it was never done **or** its recorded
Codex review was unusable (empty / envelope / UTF-8-fail / out-of-credits) — so after a Codex-credit refill (or
the already-committed UTF-8 fix) it re-runs **only the failed items**, not all 139, and last-wins supersedes the
stale rows. Run status is in the gitignored `benchmark_data/runs_live_accuracy/reviews.jsonl`.

**Exact command (from the repo root, `F:\overmind`):**
```bash
python -m evals.live_vendor_accuracy
```
That's it — no flags. It reads the existing `reviews.jsonl`, re-executes only the tasks whose Codex review is
unusable, then re-scores all 139 and rewrites `benchmark_data/runs_live_accuracy/scorecard.json` and prints the
arm table. (Was used successfully this pass: 51 items resumed → Codex 63%→100% usable → Arm C 0.921→0.944.)

**Cheap liveness precheck (real exec, not `codex login status` which lies):**
```bash
python -c "import sys;sys.path.insert(0,'.');from evals.live_vendor_accuracy import SshCodexBackend;print(SshCodexBackend(timeout=60).query('Reply with exactly: OK'))"
```
If it prints `OK`, Codex is live — run the resume. If it prints `... out of credits ...`, it's still blocked;
leave it primed and wait (no retry loop). Requires the laptop node up (Tailscale) + `agy` local.

*Driver: `evals/live_vendor_accuracy.py`. Raw per-task reviews + scorecard:
`benchmark_data/runs_live_accuracy/` (gitignored). Measurement-only; no harness behaviour changed;
benchmark unit tests green (130 passed / 8 skipped).*
