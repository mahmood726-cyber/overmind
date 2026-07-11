# Live-Vendor Accuracy 2026-07-10 — closing GAP #1

**Date:** 2026-07-10 · **measurement-only** (no harness behaviour changed; driver on a feature branch, held for go).
Closes the peer-benchmark's #1 open item: *the harness's evals were fixture-based; this is a real **live-vendor**
accuracy number* over a sealed, labelled corpus.

**Headline (verified-live, with an honest asterisk):** on the sealed held-out slice (n=139, 126 defects), the
harness's real cross-vendor verification path — **Arm C (Codex + agy + objective floor)** — caught
**92.1% of defects, 116/126, Wilson-95% CI [86.0%, 95.6%]**, at a false-alarm rate of 46.2% (6/13 cleans),
reduced to **30.8%** by the conformal gate while still catching 86.5%. **The asterisk:** the Codex lane was
**degraded to 63% usable** this pass (a UTF-8 stdin bug in my driver — now fixed — plus the Codex seat running
out of credits mid-run), so the number is carried mainly by **agy + the deterministic floor** (0.873), with the
degraded Codex adding a real but modest **+4.8pp**. It is therefore a **conservative floor**: a healthy Codex
lane would match or exceed it. This is a genuine live-vendor number, honestly bounded — not a clean
two-healthy-frontier-vendor measurement.

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

**Vendor usable-rate this pass:** agy **124/139 = 89%** (healthy); Codex **88/139 = 63%** (DEGRADED — see §2a).
Both clear the `MIN_USABLE_RATE=0.5` valid-measurement bar, so no arm is INVALID; but the Codex degradation is
material and disclosed.

**Decomposition (every row scored by the harness's own `score_arm`; a single live pass, no seed averaging):**

| arm | caught-defect | Wilson 95% CI | false-alarm (n=13) | what it isolates |
|---|:--:|:--:|:--:|---|
| **objective-ref** (witness-only floor, deterministic) | **0.341** | [0.264, 0.428] | 0.000 (0/13) | the deterministic base — catches exactly the 43 witness-detectable defects, structurally misses all 83 reviewer-only |
| Codex only (**DEGRADED**, 63% usable) | 0.436 | [0.353, 0.524] | 0.308 (4/13) | single-vendor baseline — artificially low (unusable → no flag) |
| agy only (89% usable) | 0.825 | [0.750, 0.882] | 0.462 (6/13) | one reliable cheap reviewer alone |
| agy + floor | 0.873 | [0.804, 0.920] | 0.462 (6/13) | one vendor + the deterministic floor |
| Codex + floor (degraded) | 0.556 | [0.468, 0.639] | 0.308 (4/13) | degraded frontier + floor |
| **★ C = Codex + agy + floor** (the harness path) | **0.921** | **[0.860, 0.956]** | 0.462 (6/13) | **heterogeneous consensus-or-flag + floor — the differentiator** |
| C + conformal gate (α=0.10) | 0.865 | [0.795, 0.914] | **0.308** (4/13) | FAR-control lever: 9 abstained (7 on defects), FAR 0.462→0.308 |

**The differentiator holds live:** C (0.921) > best single reviewer agy (0.825, +9.6pp) > degraded Codex
(0.436) > deterministic floor (0.341, +58pp from reviewers). Even a **degraded** Codex adds **+4.8pp** over
agy+floor (0.873 → 0.921) — a healthy Codex would add more.

### 2a. Honest disclosure — the Codex degradation (root-caused)
Of 51 unusable Codex reviews: **44 were a UTF-8 stdin-encoding bug in my driver** (`subprocess` used Windows'
cp1252 default, mangling non-ASCII artifact chars — em-dashes, ±, ≤ — so `codex exec` rejected the prompt as
"input is not valid UTF-8"). This is *my measurement transport*, **not** Codex or the harness — I hit my own
documented cp1252 trap. It is **fixed** in the driver (send explicit UTF-8 bytes), verified on a
previously-failing artifact. The remaining failures appeared late in the run when the **Codex mahmood726 seat
ran out of credits** ("Your workspace is out of credits"). Because only agy (google) remains live, a **clean
re-run with both frontier vendors healthy is deferred** until Codex credits return — the UTF-8 fix is already in
place, so the re-run is a one-command resume. The degraded Codex means Arm C = 0.921 is a **lower bound** on the
harness's healthy-panel accuracy.

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
- **Codex lane degraded (63% usable)** — the headline is a **lower bound**; see §2a. Fixed for the re-run.
- **agy carried the result:** agy-only 0.825, agy+floor 0.873 — so most of the caught-defect rate is **one
  reliable cheap reviewer + the deterministic floor**, and the *cross-vendor* increment this pass is only
  **+4.8pp** (with Codex degraded). Don't over-attribute the 0.921 to "two frontier vendors" — it's
  "floor + agy + partial Codex." (Notable: agy `flash_lite`, a fast/cheap model, alone caught 82.5% — the
  reviewer-only defects are catchable by careful cheap reading.)
- **False-alarm rate is the real weakness:** 46.2% raw (6/13 cleans wrongly flagged), 30.8% gated. Flag-on-any-
  dissent is trigger-happy on correct artifacts, and 13 cleans is a small denominator (wide CI). The conformal
  gate is the right lever; more clean cases are needed to pin FAR down.
- **Effort:** Codex at `reasoning_effort=medium` — conservative vs the harness default (xhigh).
- **Single live pass, no seed averaging** — mildly nondeterministic; re-running lands a slightly different point
  within the CI. Notably C-caught (0.921), C-CI, and C-FAR (0.462) **match the prior 2026-07-07 held-out run
  (Claude+agy) almost exactly** — consistent with the floor + agy dominating and the frontier vendor at the
  margin.
- **Arm B (homogeneous ×3) not run live this pass** (seat cost + Codex credits) — the live contrast here is
  single (A) vs heterogeneous (C); the B<A finding is from prior runs.

*Driver: `evals/live_vendor_accuracy.py`. Raw per-task reviews: `benchmark_data/runs_live_accuracy/reviews.jsonl`
(gitignored). Measurement-only; no harness behaviour changed.*
