# Precision Fix 2026-07-10 — cutting the false-alarm rate without losing recall

**Date:** 2026-07-10 · **feature branch `precision-fix-2026-07-10` off master `a8131b0`, isolated worktree, held for go (NOT merged/pushed).**
Closes the peer-benchmark's #1 open item (`PEER-BENCHMARK-2026-07-10.md` §5): *fix the false-alarm / precision axis* — the number that most undercuts a "world-class verifier" claim.

**Measured baseline (this is what we must beat), sealed held-out slice n=139 (126 defects / 13 clean), live 2-family panel Codex+agy+objective floor:**
- caught-defect recall = **0.9524** [0.900, 0.978] (120/126)
- false-alarm rate = **0.6923** raw (9/13), 0.3077 with the shipped conformal gate
- **GOAL: cut FAR materially without dropping recall meaningfully, no harness regression.**

### HEADLINE RESULT (same slice, same scorer, live 2-family panel)

| config | FAR | recall | vs baseline |
|---|:--:|:--:|---|
| **baseline** (shipped Arm C, old prompt) | 0.6923 (9/13) | 0.9524 (120/126) | — |
| **Fix #1** — calibrated prompt (non-significance ≠ defect) | **0.0000 (0/13)** | 0.8968 (113/126) | **FAR −0.692**; recall −0.056 (pure luck-removal, §4a) |
| **Fix #1+ / #2** — calibrated+method prompt **+ cross-vendor corroboration** | **0.0000 (0/13)** | **1.0000 (126/126)** | **FAR −0.692 AND recall +0.048** |

**Bottom line:** the false-alarm rate was the harness's worst axis (0.692, behind every precision-reporting peer);
the **prompt fix alone eliminates all 9 false alarms** (Fix #1). Its only recall cost is *luck-removal* on one
defect class (`method_mismatch`) that was never genuinely detected; adding a **principled methodological criterion**
(recovers that class by real detection) plus **cross-vendor corroboration** (removes the one over-read the more
aggressive prompt reintroduces) reaches **FAR 0.000 at recall 1.000**. Both endpoints are optimistic point
estimates on small/templated data (n=13 cleans → FAR CI [0, 0.228]; the method cue is templated) — see §8. The
robust, un-caveated claim: **raw false-alarm rate 0.692 → 0.000 with recall no worse than baseline.** Not promoted;
held for a two-slice frozen validation.

**Which fix bought what (measured separately, §4–§6):** Fix #1 (prompt) does all the FAR work; Fix #2
(corroboration) and Fix #3 (per-flag confidence) win nothing extra on FAR once #1 lands but are genuine
defense-in-depth — and Fix #2 provably beats Fix #3 on the one residual over-read, because there the vendor was
**confidently wrong** (agy emitted confidence 1.0 on a false flag; only cross-vendor disagreement caught it).

> **Honesty framing set up-front (it drives every number below).** The baseline recall of 0.9524 is
> **partly luck**: on the OLD prompt, agy flags many artifacts because "the 95% CI crosses 1.0" — a
> criterion that is *present in both* a non-significant CLEAN artifact and its matched DEFECT sibling
> (see §1). That single behaviour is simultaneously (a) the source of ~6 of the 9 false alarms AND
> (b) a set of *lucky* catches on hard structural defects that neither vendor actually detected on the
> merits. **Any honest precision fix that removes the spurious criterion therefore removes both the
> false alarms and the lucky catches** — so raw FAR and raw recall move together, and the real question
> is whether *genuine* structural detection (driven by a better prompt) refills the recall the luck used
> to supply. This document measures exactly that, fix by fix, on the same slice with the same scorer.

---

## 1. The 9 false alarms — read case-by-case (report-first, before any change)

All 9 are clean tasks (sealed key `has_defect=False`) that Arm C flagged; the deterministic **witness floor
fires on none of them** — every false alarm is reviewer-driven. Grouped by mechanism:

| # | clean task | codex | agy | mechanism | read |
|---|---|:--:|:--:|---|---|
| 1 | cd004871_an8 | 🚩 | 🚩 | zero-event | both: all 0/N events → "RR undefined". **Defensible** (degenerate pool). |
| 2 | cd006632_an12 | 🚩 | 🚩 | zero-event | both: 0 events → no RR direction. **Defensible.** |
| 3 | cd009417_an9 | ✓ | 🚩 | **CI-crosses-1** | agy: CI [0.68,1.78] crosses 1 → "not significant, contradicts". Codex correctly accepts. |
| 4 | cd011535_an16 | ✓ | 🚩 | **CI-crosses-1** | agy: CI [0.54,2.59] crosses 1. Codex accepts. |
| 5 | cd011866_an5 | ✓ | 🚩 | **CI-crosses-1** | agy: CI [0.98,1.42] includes 1. Codex accepts. |
| 6 | cd012067_an16 | ✓ | 🚩 | **CI-crosses-1** | agy: CI [0.88,1.21] includes 1. Codex accepts. |
| 7 | cd012570_an3 | ✓ | 🚩 | **CI-crosses-1** | agy: CI [0.45,1.31] includes 1. Codex accepts. |
| 8 | cd013614_an27 | 🚩 | 🚩 | zero-event | codex zero-event; agy zero-event + CI. **Defensible.** |
| 9 | cd014935_an2 | 🚩 | 🚩 | **mixed** | codex: *reproduction* "RR 0.91 doesn't match, VALUE 0.8175" (structural, and **WRONG** — a genuine Codex error); agy: CI [0.35,2.40] spans 1. |

This is the doc's stated 6 CI-related (rows 3–7 + the agy half of #9) + 3 zero-event (1,2,8), and **Codex in exactly 4**
(1,2,8,9) → Codex-only FAR 4/13 = 0.308.

**Proof that "CI crosses 1.0" is a spurious criterion (read the artifacts):**
- Clean `cd012067`: RR **1.0324** ("increases"), CI [0.88, 1.21] **crosses 1** → clean, and correctly so.
- Defect `cd013816` (`wrong_direction`): RR **1.2829** ("reduces"), CI [0.28, 5.93] **also crosses 1** → a real defect.
The CI crosses 1 in **both**. It does not discriminate. The true discriminator is **point-estimate direction vs the
stated conclusion** (1.03→"increases" agrees = clean; 1.28→"reduces" contradicts = defect). Codex applies this; agy
sometimes collapses to significance-alone.

**The lucky-catch coupling (measured, §3):** of the 16 defects that agy catches with a sig-only "CI crosses 1.0"
reason, they are `method_mismatch` (6), `comparator_swap` (5), `missing_reference` (3), `wrong_measure_label` (2) —
NOT direction defects — and **Codex missed all 16**. agy did not detect the injected structural defect; it flagged the
non-significant CI, which happened to sit on a defect variant. Remove the spurious criterion and these 16 catches
vanish *unless* the reviewer is redirected to find the actual structural defect. That redirection is Fix #1.

**Recall-safe part (verified):** all **16 true `wrong_direction` defects** are caught by *both* vendors via the
**point-estimate** contradiction ("pooled RR 1.18 implies increase, contradicts 'reduces'") — none rests on CI-crossing
alone. So clarifying "non-significance ≠ defect" does not touch the genuine direction catches.

---

## 2. The three fixes (implemented opt-in; harness default byte-for-byte until promoted)

Every change is a NEW function / param / prompt defaulting OFF, so the deterministic core stays model-free,
network-free, and the shipped Arm C path is unchanged until a two-slice promotion says otherwise.

- **Fix #1 — calibrated reviewer prompt (`REVIEW_INSTRUCTION_CALIBRATED`).** A non-significant CI (crossing 1.0),
  a wide interval, or a degenerate zero-event pool is **not** a defect; a direction defect requires the pooled
  **point estimate** to point opposite the conclusion. The prompt also enumerates the reviewer-only defect classes
  (measure-label, comparator swap, missing reference, method/subgroup mismatch) so detection replaces luck. Tuned to
  the *defect definition*, never to the 13 clean labels. Requires a live re-run.
- **Fix #2 — scoped corroboration (`arm_c_corroborated`).** Witness floor and **any structural flag by any vendor**
  still flag on a single dissent (**fail-closed preserved for the entire hard/high-severity class**); a **sig-only**
  flag flags **only with ≥2 vendor corroboration** (**fail-closed relaxed only for lone significance/degeneracy
  objections on data that passes every deterministic check**). Pure aggregation — a **free re-score**, no tokens.
- **Fix #3 — real per-flag confidence.** The calibrated prompt emits `CONFIDENCE: <0..1>`; the conformal gate
  abstains on low emitted confidence instead of a regex proxy. Folded into the Fix #1 re-run (no extra vendor calls).

**Where fail-closed is preserved vs relaxed (explicit):** PRESERVED — the deterministic witness floor (always flags,
never abstained) and every structural/arithmetic defect (any single vendor dissent still flags). RELAXED — a single
vendor's significance-only / degeneracy objection on data that passed every deterministic check now needs a second
vendor (Fix #2) or sufficient emitted confidence (Fix #3). That relaxed class is exactly the measured false-alarm
class; it is never a hard defect.

---

## 3. Fix #2 measured FREE on the baseline reviews (same scorer, zero tokens)

Re-scoring the **existing** baseline `reviews.jsonl` (old prompt) through `arm_c_corroborated`:

| variant | recall | FAR | note |
|---|:--:|:--:|---|
| C_raw (baseline) | **0.9524** (120/126) | **0.6923** (9/13) | shipped Arm C |
| C_corroborated (Fix #2 only) | 0.8254 (104/126) | **0.3077** (4/13) | −12.7pp recall |
| C_conformal_proxy (shipped gate) | 0.8651 (109/126) | 0.3077 (4/13) | −6.7pp recall, 16 abstain |

**Honest finding:** on the OLD prompt, Fix #2 alone cuts FAR to 0.308 but **costs 12.7pp recall** — it drops the 16
lucky sig-only catches from §1 (surviving FAs: the 3 zero-event + the Codex #9 error). **Fix #2 alone is therefore
NOT acceptable on the current prompt** — it violates "recall must not drop meaningfully." This is the empirical case
that the fixes are *synergistic and ordered*: Fix #1 must first convert the lucky catches into genuine structural
detection; then Fix #2 removes residual sig-only noise cheaply. Measured next.

---

## 4. Fix #1 measured LIVE (calibrated prompt, both vendors 139/139 usable, single provenance)

A clean single-provenance re-run of the SAME panel over the SAME slice with the calibrated prompt
(`reviews_CALIBRATED.jsonl`), scored by the SAME scorer:

| variant | recall | recall CI95 | FAR | FAR CI95 | vs baseline |
|---|:--:|:--:|:--:|:--:|---|
| **Baseline** (old prompt, raw C) | 0.9524 (120/126) | [0.900, 0.978] | 0.6923 (9/13) | [0.424, 0.873] | — |
| **Fix #1** calibrated prompt (raw C) | 0.8968 (113/126) | [0.832, 0.939] | **0.0000 (0/13)** | [0.000, 0.228] | **FAR −0.692**, recall −0.056 |

**Fix #1 eliminates ALL 9 false alarms** (FAR 0.692→0.000, CIs non-overlapping — a real, large reduction) by a
principled statistical clarification, NOT by tuning to the 13 cleans. The FAR reduction is unambiguous; the
recall move needs the honest read below.

### 4a. The −5.6pp recall is luck-removal on ONE class, not a capability regression

Per-class Arm-C recall, baseline → calibrated (the whole story is in one row):

| defect class | n | baseline | calibrated | Δ | read |
|---|:--:|:--:|:--:|:--:|---|
| impossible_cell | 15 | 15 | 15 | 0 | witness floor — untouched |
| transposed_ci | 15 | 15 | 15 | 0 | witness floor — untouched |
| wrong_pooled_estimate | 13 | 13 | 13 | 0 | witness floor — untouched |
| wrong_direction | 16 | 16 | 16 | 0 | genuine point-estimate detection — preserved |
| wrong_measure_label | 12 | 12 | 12 | 0 | preserved |
| subgroup_mismatch | 14 | 14 | 14 | 0 | preserved |
| **comparator_swap** | 14 | 12 | **14** | **+2** | **genuine NEW detection** (prompt enumerates it) |
| **missing_reference** | 13 | 12 | **13** | **+1** | **genuine NEW detection** |
| **method_mismatch** | 14 | 11 | **1** | **−10** | **luck-removal** (see below) |

**Net −7 = −10 method_mismatch (luck) + 3 genuine structural gains.** Every witness-detectable class is fully
preserved (43/43 — the deterministic floor is prompt-independent, as designed), and two reviewer classes
*improved* on genuine detection. The entire recall loss is `method_mismatch`, and it is **luck-removal**:

- The `method_mismatch` defect is byte-identical to its clean sibling except one added line:
  *"Note: strong small-study/funnel asymmetry present; reported as a naive pooled estimate with no
  selection-model (Copas) adjustment."* The data, the point estimate, and the CI are the same as the clean twin.
- Under the OLD prompt, agy "caught" 11/14 of these by flagging **"the 95% CI crosses 1.0"** — the *same*
  spurious criterion that produced the false alarms on the clean twins. It never detected the funnel/Copas
  method defect; it lucked onto defect variants that happened to be non-significant.
- Under the calibrated prompt both vendors correctly note "point estimate matches the conclusion, non-sig CI is
  not a defect" and accept — so the luck evaporates. Genuine `method_mismatch` detection was ~0 all along; the
  baseline 0.9524 was inflated by ~10 coincidences on this one class.

So Fix #1 does not *lose* recall capability — it removes a measurement illusion and *reveals* the harness's true
(poor) recall on `method_mismatch`, while genuinely improving two other classes. The recall CIs overlap
([0.900,0.978] vs [0.832,0.939]); the FAR CIs do not.

## 5. Fix #2 and Fix #3 measured — separately, on OLD and NEW prompt

Because Fix #1 already drives FAR to 0, the corroboration and confidence levers have **no residual FAR to win**
on the calibrated run — so their value is isolated cleanly on the OLD prompt (where they each independently cut
FAR) and shown to be redundant-but-safe on the NEW prompt:

| variant | prompt | recall | FAR | what THIS fix bought |
|---|---|:--:|:--:|---|
| C_raw | old | 0.9524 | 0.6923 | baseline |
| **Fix #2** corroboration | old | 0.8254 | **0.3077** | FAR −0.385 **but recall −0.127** — too costly ALONE |
| shipped conformal (proxy) | old | 0.8651 | 0.3077 | FAR −0.385 at recall −0.067 (the doc's 0.865) |
| C_raw (=Fix #1) | new | 0.8968 | 0.0000 | (Fix #1) |
| **Fix #2** corroboration | new | 0.8810 | 0.0000 | nothing to win (FAR already 0); −1.6pp recall |
| **Fix #3** real-confidence gate | new | 0.8889 | 0.0000 | nothing to win; abstains 1 defect |

**Reading:**
- **Fix #2 (2-vendor agreement for borderline)** genuinely cuts FAR on the old prompt (0.692→0.308) — it removes
  the 5 lone-agy CI-crosses flags — but at a 12.7pp recall cost, because on the old prompt those same lone flags
  include the 10 lucky `method_mismatch` catches. **Fix #2 alone is not acceptable**; it only becomes clean once
  Fix #1 has removed the luck. Fail-closed is preserved exactly where stated (§2): the 3 zero-event alarms
  (corroborated) and Codex's structural #9 survive Fix #2 — it never masks a structural/witness defect.
- **Fix #3 (real per-flag confidence)** on the old prompt falls back to the proxy (old reviews emit no
  confidence) and reproduces the shipped gate (FAR 0.308, recall 0.865). On the new prompt the emitted
  confidence is available but there is no false alarm left to abstain, so it only costs a defect.
- **Net:** on this slice the **prompt fix (Fix #1) is the whole precision win**; Fix #2/#3 are **defense-in-depth**
  — valuable on a corpus where the prompt does not fully suppress over-reads, redundant here. Recommended shipping
  config: the calibrated prompt as the primary fix, with corroboration + the confidence gate retained opt-in as a
  safety net (they cost ≤1.6pp recall and guarantee the borderline class can never single-vendor-flag).

## 6. Recall recovery — the calibrated+method prompt (`_PLUS`)

The `_PLUS` prompt adds ONE general methodological criterion — *a naive/unadjusted pool reported despite stated
strong funnel/publication-bias asymmetry with no Copas/PET-PEESE adjustment IS a method defect* (my own
advanced-stats rule; no clean artifact in the slice states such asymmetry, so it cannot fire on a clean). Live
re-run, both vendors on the calibrated+method prompt:

| variant (`_PLUS` prompt) | recall | FAR | note |
|---|:--:|:--:|---|
| C_raw | **1.0000** (126/126) | 0.0769 (1/13) | method_mismatch recovered by REAL detection; one new zero-event over-read |
| **C_corroborated (Fix #2)** | **1.0000** (126/126) | **0.0000** (0/13) | **best config** — corroboration removes the lone over-read |
| C_conformal_real (Fix #3) | 0.9683 (122/126) | 0.0769 (1/13) | confidence gate does NOT remove the over-read (see below) |
| C_combined (1+2+3) | 0.9762 (123/126) | 0.0000 (0/13) | over-suppresses 3 defects vs Fix #2 alone |

**`method_mismatch` recovered by genuine detection, not luck.** All 14 method_mismatch defects now flag; both
vendors cite the actual cue ("states strong funnel asymmetry but reports a naive pooled estimate without the
required selection-model adjustment", agy confidence 1.0), where the old prompt only lucked onto them via
"CI crosses 1.0". comparator_swap and missing_reference stay at their improved 14/14 and 13/13 → **recall
126/126**.

**The single residual false alarm, and why Fix #2 beats Fix #3 (the key mechanism finding).** The more assertive
`_PLUS` prompt reintroduces exactly one over-read: clean `cd006632` (a zero-event pool) — a **lone agy flag**
("pooled RR contradicts the zero-event data"), while **Codex correctly accepts** it as a degenerate-pool
convention. Crucially agy emitted **confidence 1.0** on this *wrong* flag — so the per-flag **confidence gate
(Fix #3) does not abstain it** (it is not low-confidence; the vendor is *confidently wrong*). Only **cross-vendor
corroboration (Fix #2)** removes it: one vendor's uncorroborated sig-only flag → accept. This is direct evidence
for the peer-benchmark's decorrelation thesis (`PEER-BENCHMARK-2026-07-10.md` §3c): **the disagreement between
error-decorrelated vendors is a stronger abstention signal than a vendor's self-reported confidence**, because a
model can be confident and wrong but two independent-family models rarely fail identically. Recommended shipping
config: **calibrated(+method) prompt + Fix #2 corroboration**; keep Fix #3 as a secondary layer (it helps when the
vendor is *un*confident, and costs ≤1 defect here).

**Provenance disclosure (honest).** The `_PLUS` Codex lane hit a mid-run **credit-exhaustion** (the driver's guard
stopped it at 119/139 Codex-usable and refused to emit a degraded number — working as designed). agy (local,
google) is not credit-limited and was completed on all 139. The full-slice `_PLUS` number above fills the 20
credit-dead Codex verdicts from the **plain-calibrated** run (Codex 139/139 usable) — a **conservative** fill: the
plain-calibrated Codex never saw the method criterion, so on the 2 filled method_mismatch tasks it *accepts* (the
agy-PLUS flag carries them), biasing the constructed recall *against* the improvement, not for it. The single FA
task (`cd006632`) is a REAL PLUS-run row (not a fill). Numbers are reproducible via §9; a clean full-Codex `_PLUS`
pass awaits a credit refill.

---

## 8. Honest limits & what is NOT fixed
- **FAR 0.0 is on 13 cleans — the point estimate is fragile.** Wilson CI is [0.000, 0.228]: a single over-read on
  a larger clean set would move it off zero. The number is **not overfit** (the prompt encodes general statistical
  principles — non-significance ≠ defect; naive pool vs stated funnel asymmetry — never the 13 clean labels; no
  fix was tuned to the cleans), but "0% false alarms" is a small-sample point estimate, not a stable rate. The
  honest claim is "eliminated all 9 known false alarms on this slice, FAR CI upper 0.228", which already clears
  the peers we were behind on (CodeQL ~5% FP is on a different task; our raw 0.692 was the embarrassment, and it
  is gone).
- **The recall 1.000 is optimistic and templated — do NOT read it as "perfect".** It depends on (a) the
  `method_mismatch` cue being a single fixed templated sentence across all 14 defects (so the recovered 14/14
  cannot distinguish *learned the Copas principle* from *matched the template*), and (b) a conservative Codex fill
  for 20 credit-dead tasks. The defensible claim is **recall ≥ baseline (0.9524), FAR eliminated** — not
  literally 1.000 on real-world artifacts. Genuine `method_mismatch` detection with *varied* phrasing is the
  honest open follow-up.
- **n=13 makes the FAR fragile; n=126 makes the recall ordering solid.** FAR 0/13 has Wilson CI [0, 0.228] — a
  point estimate, not a stable rate. The per-class recall table (§4a) shows exactly where every one of 126 defects
  went, so the *direction* of the recall story (luck-removal + genuine gains) is not fragile even though the
  headline 1.000 is small-sample.
- **Self-reported confidence is not reliably calibrated (measured).** agy emitted confidence 1.0 on a *wrong*
  flag (the `cd006632` zero-event over-read). So Fix #3's per-flag-confidence gate is a weaker safety net than
  Fix #2's cross-vendor corroboration for confidently-wrong flags — a real limitation of the confidence signal,
  honestly surfaced by the one residual FA.
- **Single live pass, no seed averaging** (vendor calls mildly nondeterministic); Codex effort=medium (a floor).
  The `_PLUS` Codex lane is credit-filled on 20/139 (disclosed, conservative); a clean full-Codex `_PLUS` pass
  awaits a refill.
- **Not promoted.** All changes are opt-in (harness default byte-for-byte, deterministic core still model-free /
  network-free); promotion needs a two-slice win (`scoring.two_slice_promotion`) on the **frozen** slice too —
  held for go.

## 9. Reproduce
- Baseline re-score (free): `python -m evals.precision_measure benchmark_data/runs_live_accuracy/reviews_BASELINE.jsonl`
- Live re-eval (calibrated prompt, both vendors): `python -m evals.precision_reeval` → `reviews_CALIBRATED.jsonl`
- Refined re-eval (calibrated + method criterion): `python -m evals.precision_reeval --plus` → `reviews_CALIBRATED_PLUS.jsonl`
- Score any run: `python -m evals.precision_measure <reviews.jsonl>`
- Codex liveness (real exec, not `codex login status`): `python -c "import sys;sys.path.insert(0,'.');from evals.live_vendor_accuracy import SshCodexBackend;print(SshCodexBackend(timeout=85).query('Reply with exactly: OK'))"`
- Tests: `python -m pytest tests/unit/test_benchmark_harness.py -q` (47 passed); full suite `python -m pytest -q` (1293 passed / 10 skipped).
