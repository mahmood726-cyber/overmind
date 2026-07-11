# Live-Vendor Accuracy 2026-07-10 — closing GAP #1

**Date:** 2026-07-10 · **measurement-only** (no harness behaviour changed; driver on a feature branch, held for go).
Closes the peer-benchmark's #1 open item: *the harness's evals were fixture-based; this is a real **live-vendor**
accuracy number* over a sealed, labelled corpus.

**Headline (verified-live, COMPLETE-coverage two-healthy-vendor run, both vendors 100% usable):** on the sealed
held-out slice (n=139, 126 defects / 13 clean), the harness's real cross-vendor verification path —
**Arm C (Codex + agy + objective floor)** — caught **95.2% of defects (120/126), Wilson-95% CI [90.0%, 97.8%]**,
at a **false-alarm rate of 69.2% (9/13 cleans)**. **Recall is excellent; the false-alarm rate is the real,
serious weakness** — and completing coverage made it *worse*, honestly (see below).

> **Two truth-first course-corrections happened while measuring this — both reported, not hidden.**
> (1) The first pass had the **Codex lane at 63% usable** (a cp1252 UTF-8 stdin bug in the driver + a brief
> Codex credit outage); fixing the bug and resuming lifted Codex to 100% and Arm C to 0.944.
> (2) The agy lane then had 13 **transient agy-driver crashes** (also a cp1252 output crash — env-fixed); an
> **agy-only recovery** (no Codex calls) completed agy to 100% — and that **raised caught 0.944→0.952 but pushed
> FAR 0.462→0.692**, because the 3 newly-recovered agy reviews all flagged *clean* artifacts. The earlier lower
> FAR was an artifact of *incomplete* agy coverage; this complete-coverage number is the honest one.
>
> **The cross-vendor story is tempered here (important, honest):** with a fully-healthy agy that is *already*
> high-recall (agy-only 0.921), the second vendor (Codex) adds only **+2.3pp** recall (agy+floor 0.929 → C
> 0.952) and **cannot lower FAR** — flag-on-any-dissent unions agy's false alarms, so C inherits agy's 0.692.
> This is the opposite of the degraded-agy A/B/C runs where the frontier vendor carried the panel; the measured
> cross-vendor benefit clearly depends on the vendors' relative reliability and calibration.

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

**Vendor usable-rate (complete run):** Codex **139/139 = 100%**; agy **139/139 = 100%**. A genuine
two-frontier-vendor measurement at full coverage.

**Decomposition (every row scored by the harness's own `score_arm`; a single live pass, no seed averaging).
Per Mahmood's honesty constraint, single-family rows are labelled — an agy-only panel is ONE family + the
objective floor, which is NOT cross-vendor consensus:**

| arm | caught-defect | Wilson 95% CI | false-alarm (n=13) | what it isolates |
|---|:--:|:--:|:--:|---|
| **objective-ref** (witness-only floor, deterministic) | **0.341** | [0.264, 0.428] | **0.000** (0/13) | deterministic base — catches exactly the 43 witness-detectable, misses all 83 reviewer-only |
| Codex only | 0.706 | [0.622, 0.779] | **0.308** (4/13) | single frontier vendor — lower recall, **best-calibrated (lowest FAR)** |
| Codex + floor | 0.762 | [0.681, 0.828] | 0.308 (4/13) | frontier + floor |
| **agy only** `[1-family, consensus DEGRADED]` | 0.921 | [0.860, 0.956] | 0.692 (9/13) | cheap reviewer alone — **high recall, high false-alarm** |
| **agy + floor** `[1-family + floor, consensus DEGRADED]` | **0.929** | [0.870, 0.962] | 0.692 (9/13) | the agy-only ceiling — one family + the objective floor |
| **★ C = Codex + agy + floor** `[2-family]` | **0.952** | **[0.900, 0.978]** | 0.692 (9/13) | heterogeneous consensus-or-flag + floor — the harness path |
| C + conformal gate (α=0.10) | 0.952 | [0.900, 0.978] | 0.692 (9/13) | FAR lever — **abstained 0; did NOT reduce FAR** (see §2c) |

**Honest reading of the panel:**
- **Recall:** C = 0.952 [0.900, 0.978], excellent. But the reviewer panel does most of it via **agy alone**
  (agy+floor 0.929); adding Codex is only **+2.3pp**. The floor contributes the structural base (0.341).
- **False-alarm is the serious weakness:** 0.692 (9/13). It is driven entirely by **agy** (agy-only FAR 0.692 vs
  Codex-only 0.308), and **flag-on-any-dissent unions it into C** — so a healthy, trigger-happy agy sets the
  panel's FAR and Codex's better calibration can't pull it down. **The FAR, not the recall, is what to fix.**

### 2a. The cross-vendor increment is reliability-dependent (a key honest finding)
In the degraded-agy A/B/C runs (2026-07-06/07) the heterogeneous panel beat single/homogeneous decisively,
because agy was partial and the frontier vendor carried it. Here, with **agy fully healthy and already
high-recall (0.921)**, the second vendor adds little recall (+2.3pp) and *raises* FAR exposure. **So the measured
cross-vendor benefit is not a fixed +X — it depends on the vendors' relative reliability and calibration.** This
is consistent with our own cited research (Rethinking-MoA / co-failure-ceiling): a second model helps most when
it *decorrelates errors*, not when one model already dominates. The honest claim is scoped accordingly.

### 2b. Two course-corrections during measurement (both disclosed)
1. **Codex lane (63%→100%):** 44 of 51 Codex failures were a cp1252 **UTF-8 stdin bug in my driver** (mangled
   em-dash/±/≤ → `codex exec` rejected the prompt as "input is not valid UTF-8" — my transport, *not* Codex or
   the harness; my own documented cp1252 trap). Fixed (explicit UTF-8 bytes) + **resumed** (re-ran only the 51
   Codex-failed items) → 0.921→0.944.
2. **agy lane (91%→100%):** 13 **transient agy-driver crashes** (a cp1252 crash in the agy driver's stdout print
   — fixed by forcing `PYTHONUTF8` in the driver env). An **agy-only recovery** (no Codex calls, honouring
   "route to agy, don't burn Codex") completed agy → 0.944→**0.952 caught but FAR 0.462→0.692**. Truth-first:
   completing coverage revealed agy's over-flagging that the incomplete run had hidden — the higher FAR is the
   real number, not the lower one. Resume mechanism: **§6**.

### 2c. False-alarm deep-dive — the 9 flagged cleans (the real weakness)
Categorising the 9 false alarms by the vendor's stated reason:
- **6 of 9 = agy over-reading "the 95% CI includes 1.0 → the direction claim is a defect"** (mostly agy-only:
  cd009417, cd011535, cd011866, cd012067, cd014935, + cd012570). The artifacts' conclusions are (per the sealed
  key) correctly hedged; agy treats any non-significant CI as a direction contradiction. **This is a specific,
  fixable harness weakness** — an agy reviewer-prompt/model behaviour, not a labelling problem.
- **3 of 9 = defensible zero-event / undefined-RR objections** (both vendors flag: cd004871, cd006632,
  cd013614). All studies have 0 events in both arms → the pooled RR is statistically degenerate/undefined (the
  zero-cell gotcha). A careful reviewer arguably *should* flag these — the benchmark's "clean" label for
  zero-event meta-analyses is **adversarial/debatable**, so these are not clearly errors.
- **Codex-only FAR is 0.308 (4/13)** — Codex flags the 3 zero-event cases + 1, i.e. it does **not** commit the
  CI-crosses-1 over-read. So a Codex-anchored or a better-google-model panel, or requiring **2-vendor agreement
  to flag borderline cases** (instead of flag-on-any-dissent), would cut FAR sharply. **Effective error-FAR,
  excluding the 3 defensible zero-event objections, is 6/13 ≈ 0.46 — and all 6 are the one fixable agy pattern.**
- **The conformal gate abstained 0** — the harness reviewers emit no per-flag confidence, so the gate has
  nothing to threshold. Making it control FAR needs a per-flag confidence signal. (Follow-ups, not done here —
  measurement-only task.)

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

## 5. Honest limits & follow-ups
- **False-alarm rate is the serious weakness, not recall:** 0.692 (9/13) at full coverage. **6/9 are one fixable
  agy pattern** (CI-crosses-1 → false "direction defect"); 3/9 are defensible zero-event objections. Concrete
  fixes (behaviour changes, NOT done in this measurement-only task): (a) fix agy's reviewer prompt so a
  non-significant CI is not a defect; (b) require 2-vendor agreement (not flag-on-any-dissent) for borderline
  significance flags; (c) give reviewers a per-flag confidence so the conformal gate can actually abstain
  (it fired 0 here); (d) treat zero-event/degenerate meta-analyses as a distinct labelled class.
- **Cross-vendor increment is small on this corpus** (agy+floor 0.929 → C 0.952, +2.3pp) because a healthy agy
  already dominates recall; don't generalise a large heterogeneity gain from here (see §2a).
- **Effort:** Codex at `reasoning_effort=medium` — conservative vs the harness default (xhigh).
- **Single live pass, no seed averaging**; 13 cleans is a small denominator (wide FAR CI [0.42, 0.87]).
- **Arm B (homogeneous ×3) not run live** — the live contrast is single (Codex 0.706 / agy 0.921) vs 2-family
  C (0.952); the B<A finding is from prior runs.
- **Codex is currently reachable** (a liveness probe returned `OK`), but per Mahmood's instruction further vendor
  work is **routed to agy** and Codex is not burned. The full 2-family number above was measured while Codex was
  live and stands; if Codex re-depletes, the agy-only ceiling (0.929 caught / 0.692 FAR, **consensus DEGRADED**)
  is the labelled fallback — never to be reported as a 2-family consensus number.

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
arm table. (Used successfully this pass: 51 items resumed → Codex 63%→100% usable → Arm C 0.921→0.944.)

**agy-only coverage recovery (no Codex calls — for when Codex must not be burned):**
```bash
python -m evals.live_vendor_accuracy --agy-recover
```
Re-runs **only** agy on tasks whose recorded agy review was unusable (keeping the existing Codex verdict), then
re-scores. Honours "route to agy, don't burn Codex". (Used this pass: 13 agy crashes recovered → agy 91%→100%
→ Arm C caught 0.944→0.952, FAR 0.462→0.692.) The driver also forces `PYTHONUTF8` so the agy-driver cp1252
output crash doesn't recur.

**Cheap liveness precheck (real exec, not `codex login status` which lies):**
```bash
python -c "import sys;sys.path.insert(0,'.');from evals.live_vendor_accuracy import SshCodexBackend;print(SshCodexBackend(timeout=60).query('Reply with exactly: OK'))"
```
If it prints `OK`, Codex is live — run the resume. If it prints `... out of credits ...`, it's still blocked;
leave it primed and wait (no retry loop). Requires the laptop node up (Tailscale) + `agy` local.

*Driver: `evals/live_vendor_accuracy.py`. Raw per-task reviews + scorecard:
`benchmark_data/runs_live_accuracy/` (gitignored). Measurement-only; no harness behaviour changed;
benchmark unit tests green (130 passed / 8 skipped).*
