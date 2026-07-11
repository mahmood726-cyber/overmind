# Offline Local-LLM Feasibility — can the harness run for a scientist on a laptop in Uganda?

**Date:** 2026-07-11 · **measurement-only** (no harness behaviour changed; driver + adapters on
feature branch `offline-local-llm-feasibility-2026-07-11`, held for go). This is the headline test
of the manifesto's field-deployment claim: instead of *asserting* the harness runs offline on a
modest laptop, we RUN it — the harness's real verification path over the sealed labelled slices,
with **local, CPU-only, quantized** models as the reviewer arms — and report honest numbers,
including the one that decides it: **error decorrelation between local models**.

> **VERDICT (up front): PARTIALLY SUPPORTED.** The *offline deterministic core* is fully supported —
> pooling + witness floor + structural gate run with the network hard-cut, instantly, free (§4),
> catching 34% of defects at **0%** false alarms. A *single* local reviewer (qwen2.5-7B) + that floor
> is a genuine, usable **advisory** layer (recall 0.770; by the harness's own recall−FAR blend 0.385
> it beats both the floor alone and the raw frontier baseline panel). But the manifesto's implied
> *cross-model offline consensus* is **NOT supported at the shipped operating point**: a local
> multi-model panel drives the false-alarm rate to **0.85–1.0** — it flags nearly every clean
> artifact. The decisive reason is the opposite of what you'd fear: local models are **not** more
> error-correlated than the frontier pair on *misses* (they are as well or better decorrelated); the
> panel fails on the **false-alarm** axis, because the small models hallucinate arithmetic defects
> and the harness's flag-on-any-dissent rule unions that noise. See §6 for exactly what would close
> the gap.

---

## 0. What was actually measured (and what is / isn't ours)

Accuracy is computed **entirely by the harness's own code** — the same modules the live-vendor number
used (`LIVE-VENDOR-ACCURACY-2026-07-10.md`):

- **local reviewer backend** → `overmind.verification.judge_backends.LocalModelBackend` (the
  harness's *shipped* Ollama `/api/generate` lane, `OVERMIND_LOCAL_MODEL=1`), one per model.
- **reviewer prompt + parser** → `overmind.benchmark.reviewers.BackendReviewer` — the **baseline**
  `REVIEW_INSTRUCTION`, identical to the frontier baseline run (NOT the calibrated precision-fix
  prompt — apples-to-apples with the 0.9524 / FAR 0.692 frontier baseline).
- **aggregation (A / C / floor)** → `overmind.benchmark.arms.arm_a` / `arm_c` (consensus-or-flag).
- **objective witness floor** → `overmind.benchmark.witnesses.run_witness`.
- **scoring (recall / FPR + Wilson CI)** → `overmind.benchmark.scoring.score_arm`.

The **only** new code is (a) a pure timing/RAM wrapper that forwards the prompt byte-for-byte and (b)
the decorrelation math — both measurement, neither alters a verdict. Answer keys are read **only** by
the scorer (blinding preserved). **No hand-tuning, no peeking at labels, no prompt changes** — the
shipped local lane, as-is, is what a field user would get. Driver: `evals/offline_local_accuracy.py`;
offline-core proof: `evals/offline_core_proof.py`.

## 1. The hardware this actually ran on (a genuine field-laptop envelope)

The measurement box is, by luck, close to a real field laptop — not a datacentre result:

| resource | this box | field-laptop target |
|---|---|---|
| CPU | **4 cores** (x86-64) | 4–8 cores |
| RAM | **17 GB total** | 8–16 GB |
| GPU | **none** (`nvidia-smi` absent) | none assumed |
| inference | **100% CPU** — confirmed by `ollama ps` on every one of 679 RAM samples; `OLLAMA_NUM_GPU=0` | CPU-only |

**CPU-only was enforced and verified, not assumed:** no GPU is present, and `ollama ps` reported the
loaded model as `100% CPU` throughout the entire run. Models ran **sequentially** to keep the peak
working set inside the 8–16 GB envelope.

**Model footprints (authoritative — `ollama ps` steady-state; all `100% CPU`, 4096 ctx):**

| model | arch / vendor | quant | disk | resident (loaded) |
|---|---|---|---|---|
| qwen2.5:7b-instruct | Alibaba Qwen2.5 | Q4_K_M | 4.7 GB | **5.1 GB** |
| llama3.1:8b-instruct | Meta Llama-3.1 | Q4_K_M | 4.9 GB | **5.6 GB** |
| phi3:mini (3.8B) | Microsoft Phi-3 | Q4 | 2.2 GB | **3.9 GB** |

Marginal RAM to add a 7–8B Q4 reviewer is **~5–6 GB** (3.9 GB for the 3.8B). On a clean field laptop
(OS baseline ~2–3 GB) that is a **~8 GB working set** — inside a 16 GB laptop, feasible on 8 GB with
the 3.8B model. **Caveat (real, field-relevant):** Ollama kept up to **two** models resident at once
here (default `OLLAMA_MAX_LOADED_MODELS`), so the sampled peak during a model *switch* hit **~10 GB**;
a field deployment should set `OLLAMA_MAX_LOADED_MODELS=1` to hold ~5–6 GB steady. (The in-driver RAM
sampler under-counts — the model is memory-mapped in a separate `llama-server.exe`; numbers here are
from `ollama ps` + direct runner-RSS sampling, logged to
`benchmark_data/runs_offline_local/ram_samples.jsonl`.)

**Per-task wall-clock (CPU-only, 4 cores):**

| model | held_out median | p90 | frozen median | note |
|---|:--:|:--:|:--:|---|
| qwen-7B | **17.7 s** | 28.1 s | 23.4 s | fastest despite being 7B |
| llama-8B | 24.3 s | 38.3 s | 24.6 s | |
| phi-3-mini (3.8B) | 27.3 s | 46.7 s | 30.5 s | **NOT faster** — it rambles (longer output dominates) |

Artifacts are tiny (median ~120 tokens, max 231), so latency is generation-bound, not prompt-eval.
Max outliers (up to 282–392 s) are memory-thrash spikes on this *shared* box (the Claude harness
itself held ~3.5 GB); on a dedicated laptop the medians are representative. **A realistic 30-abstract
review ≈ 9–15 min per model** on 4 CPU cores; a 100-abstract review ≈ 30–50 min. Feasible, slow, and
the "small model is faster" intuition failed — Phi-3-mini was the slowest by wall-clock because it
generates the most text.

## 2. Results — caught-defect rate & false-alarm rate (Wilson 95% CI)

### 2a. Slice 1 — held_out (n=139: 126 defects / 13 clean) — the frontier-comparable slice

| config | caught-defect (recall) | Wilson CI | false-alarm (n=13) | Wilson CI | recall − FAR |
|---|:--:|:--:|:--:|:--:|:--:|
| objective floor (no LLM) | 0.341 | [0.264, 0.428] | **0.000** | [0, 0.228] | **0.341** |
| qwen-7B + floor | 0.770 | [0.689, 0.835] | 0.385 | [0.177, 0.645] | **0.385** ★ best local |
| llama-8B + floor | 0.865 | [0.795, 0.914] | 0.769 | [0.497, 0.918] | 0.096 |
| phi-3-mini + floor | 0.913 | [0.850, 0.951] | 0.846 | [0.578, 0.957] | 0.067 |
| qwen+llama + floor | 0.960 | [0.911, 0.983] | 0.923 | [0.667, 0.986] | 0.037 |
| qwen+phi + floor | 0.992 | [0.956, 0.999] | 0.846 | [0.578, 0.957] | 0.146 |
| llama+phi + floor | 0.952 | [0.900, 0.978] | **1.000** | [0.772, 1.0] | −0.048 |
| qwen+llama+phi + floor | 0.992 | [0.956, 0.999] | **1.000** | [0.772, 1.0] | −0.008 |
| **frontier Arm C** (codex+agy+floor, **raw** baseline) | 0.9524 | [0.900, 0.978] | 0.692 | [0.424, 0.873] | 0.260 |
| frontier Arm C + conformal gate | 0.865 | [0.795, 0.914] | 0.308 | — | 0.557 |
| frontier Arm C + precision-fix prompt | 0.9524 | — | **0.000** | [0, 0.228] | **0.952** |

**Read this carefully — the headline recall numbers are a trap.** phi+floor's 0.913 and the panels'
0.95–0.99 recall look frontier-class, but they are bought by **indiscriminate flagging**: phi flags
0.913 of *defects* AND 0.846 of *cleans*. A reviewer that flags ~86% of *everything* has near-zero
discrimination. The honest columns are **FAR** and **recall − FAR** (the harness's own λ=1 blend):

- **The deterministic floor alone (0.341, FAR 0) has higher genuine discrimination than every local
  panel**, and is only edged out by **qwen-7B + floor (0.385)** — the single best offline config.
- Every multi-local-model panel is **worse than qwen+floor**, and two are **worse than the no-LLM
  floor**, because consensus-or-flag unions the members' false alarms up to FAR 1.0.
- qwen+floor (blend 0.385) even beats the **raw** frontier baseline panel (0.260) — because it is far
  less flag-happy on cleans — but loses decisively to the frontier once its precision fix lands
  (0.952). No such fix was applied to the local models (§6).

### 2b. Slice 2 — frozen (n=73: 72 defects / **1 clean**)

| config | recall | Wilson CI | FAR (n=1 — uninformative) |
|---|:--:|:--:|:--:|
| objective floor | 0.292 | [0.199, 0.405] | 0/1 |
| qwen + floor | 0.736 | [0.624, 0.824] | 1/1 |
| llama + floor | 0.875 | [0.779, 0.933] | 0/1 |
| phi + floor | 0.861 | [0.763, 0.923] | 1/1 |
| qwen+llama + floor | 0.986 | [0.925, 0.998] | 1/1 |
| qwen+phi + floor | 0.944 | [0.866, 0.978] | 1/1 |
| qwen+llama+phi + floor | 0.986 | [0.925, 0.998] | 1/1 |

The frozen recall pattern **corroborates** held_out (single models 0.74–0.88 with floor; panels
0.94–0.99). **Its FAR is uninformative — only 1 clean task** (Wilson CI on n=1 spans [0.21, 1.0]), so
it cannot confirm or deny the false-alarm story. (The brief cited slice 2 as 92 = 72/20, but the
corpus has only **33 clean tasks total** across all three deterministic slices, so a 72-defect /
20-clean frozen slice is not reconstructable from the harness's sealed `frozen_ids` split; we use the
harness's own slice and disclose. The clean-side evidence therefore rests on held_out's 13 cleans —
the same small denominator the frontier run carried.)

### 2c. The no-LLM baseline (deterministic floor alone)

Measured **offline, network cut** (§4): the floor catches **43/126 = 0.3413 [0.264, 0.428]** on
held_out at **FAR 0.000** — exactly reproducing the live-vendor doc's 0.341. This is the free,
reliable floor every configuration sits on. **It never false-alarms, because it actually computes the
2×2 arithmetic** — precisely the check the local models get *wrong* (§3).

## 3. THE CRUX — error decorrelation between local models

A *panel* pays only if members miss *different* defects and false-alarm on *different* cleans. If the
local models co-fail on the *same* items far more than the frontier pair, the consensus benefit
collapses on-device. **The measured answer is nuanced and it is the most important finding here.**

**Co-failure, φ = correlation of the two 0/1 failure vectors (0 = independent, + = fail together):**

| pair | co-MISS on defects (held_out) | co-FALSE-ALARM on cleans |
|---|---|---|
| **FRONTIER codex \| agy** | both miss **6/126**, obs 0.048 vs indep 0.014, **φ = +0.34** | both FA **4/13**, **φ = +0.44** |
| local qwen \| llama | both miss 9/126, **φ = −0.15** | both FA 3/13, φ = −0.32 |
| local qwen \| phi | both miss 3/126, **φ = −0.18** | both FA 5/13, φ = +0.34 |
| local llama \| phi | both miss 7/126, φ = +0.14 | both FA 8/13, φ = −0.23 |

**Finding 1 — decorrelation on the MISS axis is FINE (even better than frontier).** Local pairs
co-miss defects at φ ≈ −0.18…+0.14 — as well or *better* decorrelated than the frontier pair's
+0.34. So the fear "local models fail identically" is **false**. On paper this should make a panel
work: qwen+phi+floor reaches recall 0.992.

**Finding 2 — but decorrelation is IRRELEVANT here, because the binding failure is the false-alarm
BASE RATE, not correlation.** llama and phi individually false-alarm on **77% and 85%** of cleans.
When ~80% of clean artifacts trip at least one member, the harness's *consensus-or-flag* rule (any
dissent → flag) unions that noise and the panel's FAR climbs to **0.92–1.0** — it flags nearly every
clean. No amount of miss-decorrelation rescues a panel whose members each cry wolf 80% of the time.
**The frontier panel worked because Codex was well-calibrated (FAR 0.31); the local set has no member
below qwen's 0.385.**

**Finding 3 — the genuine-value decomposition (the number that cuts through the flag-happiness).**
The floor already catches all 43 witness-detectable (arithmetic) defects for free; a reviewer's only
real job is the **83 reviewer-only** defects (narrative / direction / method — invisible to the
floor). Informedness there = reviewer-only-recall − FAR:

| model | reviewer-only recall | FAR | **informedness** |
|---|:--:|:--:|:--:|
| qwen-7B | 0.651 | 0.385 | **+0.266** — genuine, between the two frontier models |
| llama-8B | 0.795 | 0.769 | +0.026 — near chance |
| phi-3-mini | 0.867 | 0.846 | +0.021 — near chance |
| frontier codex | 0.687 | 0.308 | +0.379 |
| frontier agy | 0.904 | 0.692 | +0.211 |

Only **qwen-7B** is a genuinely discriminating reviewer (informedness +0.266, sitting *between*
frontier Codex +0.379 and agy +0.211). llama and phi are effectively random flaggers.

**Finding 4 — the false alarms are REAL hallucinated arithmetic, not a parsing artifact (verified on
raw output).** On clean artifacts the small models confidently invent impossible cells: llama —
*"events 4 + 4 exceed total N 402"* (arithmetically nonsense); qwen/phi — *"events > N in all cells"*
on data where the deterministic witness confirms none. They are **noisily re-doing, and getting
wrong, exactly the 2×2 arithmetic the deterministic floor does perfectly and for free** — so the LLM
layer *adds* false-alarm noise on top of a reliable floor, on the checks the floor already owns.

## 4. Offline proof — the deterministic core runs with the network HARD-CUT

Not asserted — enforced. `evals/offline_core_proof.py` installs a per-process socket black-hole
(every non-loopback `connect`/`getaddrinfo` raises `OfflineViolation`), **verified by a self-test
that a real outbound `connect` to `8.8.8.8:53` is blocked**, then runs the full deterministic battery
(`benchmark_data/runs_offline_local/offline_core_proof.json`):

- network black-hole **enforced** (self-test confirmed the block);
- **330 tasks** processed, witness battery fired on **99**, pooling **re-computed on 297** — all with
  the network cut;
- wall-clock **0.23 s**; objective floor per slice computed offline (held_out 0.3413, FAR 0.000).

The run **completing** with every non-loopback socket blocked is the proof: pooling + witness floor +
structural gate make **zero** network calls. (We deliberately did not physically down the NIC — that
would sever this session and loopback-only Ollama is irrelevant to the deterministic core; the
per-process socket cut is a strictly stronger, reproducible guarantee for the code under test.) The
local LLM lane, too, talks only to `localhost:11434` — no external endpoint anywhere in the path.

## 5. The data problem — what an offline corpus costs, and where "open-access only" breaks

| corpus | size | count | role |
|---|---|---|---|
| **AACT** (ClinicalTrials.gov full mirror, ctti-clinicaltrials.org) | **~2.3 GB** (PostgreSQL dump or flat files) | >500,000 trials | discovery **+ structured arm-level summary results** |
| **PubMed/MEDLINE annual baseline** | **~25–30 GB** compressed (~200 GB uncompressed) | ~37–38 M citations (1,274 `.xml.gz`) | find/screen — **abstracts + metadata, NO full text** |
| **PMC Open Access subset** (XML/text) | **~120–160 GB** | ~3.4 M articles | full text — but only the OA-licensed minority |
| local vector index (abstracts) | ~15–60 GB (quant-dependent) | — | offline retrieval |

- **Minimal working set ≈ 50–70 GB** (AACT + PubMed baseline + index) — a realistic one-time USB /
  sneakernet transfer. **Full-text tier ≈ 200 GB** (add PMC OA). A PDF mirror runs to multiple TB —
  out of scope for a field laptop. All fit on a 1 TB laptop except the PDF mirror. All free, no login,
  no paywall to *download*.
- **Where the open-access chain HOLDS end-to-end:** trial discovery (AACT), abstract-level screening
  (PubMed), and **pooling of registry-posted summary results** (AACT results tables give arm-level
  effect data with no journal PDF needed) — the genuine rescue for offline synthesis.
- **Where it BREAKS:** full-text data extraction for the **majority of trials whose numeric outcomes
  live only in paywalled journal articles absent from PMC OA**. An honest offline harness must lean on
  **AACT structured results as its primary quantitative source**, treat PMC OA as a bonus minority,
  and **explicitly flag every "evidence only in a paywalled paper" trial as not-extractable-offline**
  rather than silently dropping it — otherwise the synthesis is biased toward the open subset.

Sources: AACT downloads (aact.ctti-clinicaltrials.org/downloads); PubMed baseline
(ftp.ncbi.nlm.nih.gov/pubmed/baseline, nlm.nih.gov techbull JF25); PMC OA
(pmc.ncbi.nlm.nih.gov/tools/openftlist, registry.opendata.aws/ncbi-pmc); CT.gov half-million
(nlmdirector.nlm.nih.gov, 2025-04-02).

## 6. Verdict — is the manifesto's Uganda claim supported?

**PARTIALLY SUPPORTED**, decomposed by the three things the claim actually requires:

| manifesto premise | verdict | evidence |
|---|---|---|
| "no reliable internet" (runs offline) | ✅ **SUPPORTED** | deterministic core proven network-free (§4); local LLM lane is loopback-only |
| "no frontier API" (local models suffice as reviewers) | ⚠️ **PARTIAL** | a *single* calibrated local model (qwen-7B) + floor is a usable advisory reviewer (informedness +0.266); a local *panel* is **not** — FAR 0.85–1.0 |
| "no paywalled full text" (open corpus suffices) | ⚠️ **PARTIAL** | open chain holds for discovery + screening + registry-results pooling (~50–70 GB); **breaks** at paywalled full-text extraction (§5) |
| hardware (modest laptop) | ✅ **SUPPORTED** | ~5–6 GB/model, 100% CPU, ~50–70 GB data; ~10–15 min per 30-abstract review on 4 cores |

**The one-line finding:** local models are *not* the failure mode people expect (they are **not**
more error-correlated than the frontier pair, and one of three — qwen — is a genuinely useful
reviewer). The failure mode is **calibration**: the small models hallucinate arithmetic defects on
clean data, and the harness's flag-on-any-dissent panel compounds those false alarms to the point of
flagging everything. So the manifesto's *offline consensus of cheap local models* does **not**
transfer at the shipped operating point — but a *deterministic floor + one advisory local model*
does, and that is a real, honest offline capability.

**What would have to be true to close the gap (concrete, none done here — measurement-only):**
1. **FAR control on local models.** Apply the calibrated precision-fix prompt (which cut the frontier
   FAR 0.692 → 0.000) to the local lane. The local false alarms are the *same* family
   (hallucinated-arithmetic / significance over-reads) the fix targeted — a promising, untested
   follow-up. This is the single highest-value next experiment.
2. **Corroboration aggregation instead of any-dissent.** Require ≥2 members to agree before flagging
   (the harness's `arm_c_corroborated`, Fix #2). This needs ≥2 *calibrated* members; today only qwen
   qualifies, so it must be paired with a second genuinely-discriminating small model — **not** llama
   or phi as-shipped.
3. **A better small partner for qwen** (or a larger local model), selected by measured informedness,
   not size — phi-3-mini (smallest) and llama-8B (largest here) were both near-random; size did not
   predict quality.
4. **Ship the honest floor today:** deterministic core + qwen-7B as a *single advisory* reviewer,
   never the sole gate; flag paywalled-only trials as not-extractable rather than dropping them.

## 7. Honest limits
- Single pass, no seed averaging; local models mildly nondeterministic (Ollama default temperature).
- **Baseline prompt** (not the calibrated precision-fix prompt) — deliberately matched to the frontier
  baseline for a fair comparison; a calibrated *local* prompt is the top untested follow-up (§6).
- FAR denominators are small (13 held_out cleans; 1 frozen clean) — the same small-clean limitation
  the frontier run carried; recall (126 + 72 defects) is well-powered.
- Wall-clock outliers (≤392 s) reflect memory contention on this shared box (Claude harness ~3.5 GB);
  the model-marginal RAM (~5–6 GB) and the medians are the field-relevant figures, not the 16.8 GB
  system peak.
- Not promoted; no harness behaviour changed; deterministic core still model-free / network-free.

*Artifacts: `benchmark_data/runs_offline_local/{reviews_offline.jsonl, offline_scorecard.json,
offline_core_proof.json, timing.jsonl, ram_samples.jsonl}`. Driver `evals/offline_local_accuracy.py`
+ proof `evals/offline_core_proof.py` on branch `offline-local-llm-feasibility-2026-07-11`
(measurement-only, held for go).*
