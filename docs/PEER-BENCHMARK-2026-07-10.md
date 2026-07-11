# Peer Benchmark 2026-07-10 — Our Harness vs. Comparable Systems (thorough, well-sourced)

**Date:** 2026-07-10 · **report-only, no code changes, frozen repos untouched.**
Companion to [`SYSTEMS-BENCHMARK-2026-07-10.md`](SYSTEMS-BENCHMARK-2026-07-10.md). A search-heavy head-to-head
against named, comparable systems in every category our harness spans, with each peer's capability claims
sourced to a paper / README / benchmark and scored **only** on what matters for our purpose.

**Purpose anchor (do not drift):** *a truth-gated, heterogeneous-vendor **reproduction-and-verification**
orchestrator for quantitative **evidence-synthesis** — reproduce a pooled estimate from open data, cross-check
it across **independent vendors**, bind the verdict to **objective witnesses**, and **flag/abstain** rather
than emit a wrong "pass."*

**Grounding (verified this pass, not memory):** `master` HEAD `a650361` ("enforce fail-closed consensus in the
live judge decision", on `origin/master`); **1277 test functions** (`grep -rho "def test_"` = 1277, exact);
deterministic consensus core = `overmind/review/consensus.py` + `cluster-harness/harness/consensus.py`;
reproduction eval = `evals/reconstruct_and_beat.py` (7/7 published meta-analyses reconstructed, cross-checked to
R/metafor ≤1e-4); live cross-vendor round today (Codex+agy+deterministic: 3 ACCEPT / 2 FLAG, all correct).

> **Honesty labels.** 🟢**L** verified-live today · 🟡**F** ours, fixture/code-only (logic proven, not
> live-vendor accuracy) · **★** peer, **publicly benchmarked** (number cited) · **✎** peer, paper/README-claimed
> (not re-run by me) · **—** absent / not a goal. **No peer system was executed for this doc.** Every peer
> number is self-reported and should be read as an *upper bound* — the memory-benchmark literature itself warns
> that independent reproductions land well below vendor claims (e.g. Mem0 self-reports 91.6% LoCoMo, independent
> repro **58–66%**).

---

## 0. Measured update (2026-07-10, refresh) — the two "no-number" gaps are now closed

Since the first cut of this doc, two of our 🟡F ("we have code, no published number") cells became measured 🟢L
(master `a8131b0`, 1282 tests green):

- **Live cross-vendor verification** (sealed held-out A/B/C slice, n=139, both vendors 100% usable, single pass,
  Codex effort=medium): **caught-defect 0.9524 [0.900, 0.978]** (120/126); decomposition floor 0.341 → agy-only
  0.937 → C 0.9524; **false-alarm 0.692 raw → 0.308 with the conformal gate** (gate engaged: 16 abstentions,
  recall→0.865). See `LIVE-VENDOR-ACCURACY-2026-07-10.md`.
- **Memory retrieval recall@k** (our shipped `MemoryStore`, hybrid): **LongMemEval_s R@10 96.4%** (n=500) /
  **LoCoMo R@10 45.8%** (n=1982). See `MEMORY-RECALL-BENCHMARK-2026-07-10.md`.

**These numbers force two honest revisions, made in full below:** (1) the cross-vendor claim moves from *recall*
to *calibration/precision* (§3c — the recall increment is only +1.6pp); (2) our false-alarm rate and our LoCoMo
recall are now measured and, on those axes, we are **behind** named peers (§4).

---

## 1. Peer landscape, by relevance to our purpose (with sourced numbers)

### Tier 1 — direct niche peers (automated evidence-synthesis reproduction / verification)

The systems that actually share our job. Being fair to them **narrows** the lead honestly.

- **meta-pipe** ✎ — [arXiv 2606.28363](https://arxiv.org/html/2606.28363). Full SR/MA pipeline on **the same R
  stack we use** (`meta`, `metafor`, `gemtc`, `netmeta`) + Claude (Opus 4 / Haiku 3.5), 10 stages, 5 human gates.
  Already ships **overclaim detection** (12 patterns) and **reads effect estimates directly from R output to
  prevent hallucination** — so provenance-binding and fabrication-linting are **not uniquely ours**. **But:**
  single-model (Claude-only; "portability not tested"), **generative not a verifier** ("no validation data are
  reported"), and its test-retest is two passes of the *same* model — the authors explicitly call it
  "intra-model stability, **not** inter-rater reliability." That concession independently corroborates our
  heterogeneity thesis. Cost ~$15–30/review.
- **ARA (Agentic Reproducibility Assessment)** ★ — [arXiv 2605.02651](https://arxiv.org/html/2605.02651v1).
  Turns a paper into a workflow graph, scores **reconstructability from text**. **Cross-model** (Gemini/GPT-4/Qwen
  for robustness) and **publicly benchmarked: 60.98% ReScience C, 60.71% ReproBench (vs 36.84% ReplicatorAgent),
  61.68% GoldStandardDB (vs 43.56% ReproScreener).** **But:** document-level only — **it does not execute or
  reproduce anything**, so it can't bind to run witnesses, and (its own caveat) it is "systematically optimistic."
- **Reproduction benchmarks** ✎ — CORE-Bench, PaperBench, REPRO-Bench, **ReplicatorBench**
  ([2602.11354](https://arxiv.org/html/2602.11354v1)): best model averages **~43.4%** replication — the field is
  real but immature.

### Tier 2 — verification primitives we compose

- **Mixture-of-Agents / judge ensembles** — MoA reaches **65.1% AlpacaEval 2.0 vs GPT-4o 57.5%**
  ([2406.04692](https://arxiv.org/html/2406.04692v1)); **PoLL** panels of disjoint small families beat a single
  large judge at lower cost and less intra-model bias ([2404.18796](https://arxiv.org/abs/2404.18796)).
  **Honest counterpoint (must state):** *Rethinking MoA* ([2502.00674](https://arxiv.org/pdf/2502.00674)) finds
  **mixing *different* models is NOT automatically better** — **Self-MoA** (many samples from the single best
  model) matches or beats heterogeneous mixes when one model dominates; "budget allocation matters more than
  source diversity per se." Also *When Agents Disagree* ([2603.20324](https://arxiv.org/pdf/2603.20324)) flags a
  **selection bottleneck** in multi-agent pipelines. → see §3c for why this critique targets *generation
  quality*, not *error-catch verification*.
- **Co-failure ceiling** ★ — [2606.27288](https://arxiv.org/abs/2606.27288): ensemble accuracy ≤ **1 − β**
  (β = all-wrong rate); on **checkable** tasks combining rarely beats the single best model *without a
  query-level routing signal*, and **low-ρ heterogeneous ensembles beat high-ρ ones** — the theory that both
  bounds and justifies cross-vendor verification.
- **CompassVerifier** ★ — [2508.03686](https://arxiv.org/abs/2508.03686) (EMNLP 2025): a **trained** robust
  verifier / reward model (the learned-verifier tier we lack).
- **Conformal / abstention verifiers** ★ — **CAP** ([PMLR v304](https://proceedings.mlr.press/v304/tayebati26a.html)):
  ≥target coverage, **+22.2% hallucination-AUROC, >70% lower calibration error**; **SCOPE** selective conformal
  *pairwise LLM judging* ([2602.13110](https://arxiv.org/html/2602.13110v3)); **ToolChain-CRC**
  ([2606.18467](https://arxiv.org/pdf/2606.18467)); conformal abstention for factuality
  ([2405.01563](https://arxiv.org/pdf/2405.01563)). These give **formal finite-sample abstention guarantees** we
  do not.
- **Groundedness / hallucination scorers** ★ — Vectara **HHEM-2.1-open** (110M): **claim-wise 67.1% acc / 62.7%
  F1; summary-wise 65.8% / 59.6%** ([faithfulness leaderboard](https://arxiv.org/html/2505.04847v2)). Sobering
  context: on the refreshed 32K-token leaderboard, **reasoning models hallucinate *more* on grounded
  summarization — GPT-5, Claude Sonnet 4.5, Grok-4, Gemini-3-Pro all >10%, Grok-4-fast-reasoning 20.2%**
  ([Vectara HHEM-2.1](https://www.vectara.com/blog/hhem-2-1-a-better-hallucination-detection-model)). i.e. even
  SOTA text-groundedness sits at ~67% F1 — which is exactly why our gate binds to a **computed** ground-truth
  (R/metafor) instead of scoring text.

### Tier 3 — adjacent stack

- **Agent-orchestration frameworks** ✎ — LangGraph (durable checkpoint + time-travel; wins latency/cost
  ≈**$0.08/task**), CrewAI (time-to-production), **AG2/AutoGen** (GroupChat, 9 orchestration patterns,
  conversational multi-agent consensus-by-debate; wins open-ended reasoning at **5–6× the cost**; MS AutoGen now
  maintenance-mode, AG2 the community fork), OpenAI Agents SDK (handoffs, OpenAI-only), Claude Agent SDK
  (subagents, Claude-only), Google ADK, **Magentic-One** (Orchestrator + task/progress ledger,
  [2411.04468](https://arxiv.org/html/2411.04468v1)). General-agent leaderboards: **GAIA** — Claude Sonnet 4.5
  **74.6%** (Princeton HAL; top-6 all Anthropic); **SWE-bench Verified** — Opus 4.7 **87.6%**; **τ2-bench** — Opus
  4.6 leads ([agentic leaderboard](https://awesomeagents.ai/leaderboards/agentic-ai-benchmarks-leaderboard/)).
  **Purpose note:** these benchmarks measure *general task completion*, **not truth-gated reproduction** — they
  are orthogonal to our job, so "we don't appear on GAIA" is a scope difference, not a deficit. None of these
  frameworks ships a truth-gate primitive; AG2's "consensus" is LLM agents agreeing in conversation, not a
  deterministic fail-closed gate.
- **AI static-analysis / pre-commit gates** ★ — **semgrep** (AST rules; AppSec cross-file dataflow → **−25% FP /
  +250% TP**; **82% acc / 12% FP**; median **10s** CI; Assistant auto-triage 95% agreement), **CodeQL** (deepest
  dataflow, **88% acc / 5% FP**), **Snyk/DeepCode AI** (symbolic+ML on 25M dataflow cases, OWASP +20 pts, ~80%
  auto-fix), **Qodo** (best F1 **60.1%**, recall 56.7%), **CodeRabbit** (**59.39% acc / 36.19% F1** OpenSSF CVE —
  misses ~41%), **DeepSource** (<5% FP), **VibeGuard** (**100% R / 89.5% P** on 8 projects,
  [2604.01052](https://arxiv.org/abs/2604.01052)) ([SAST comparison](https://sanj.dev/post/ai-code-security-tools-comparison/),
  [code-review benchmark](https://entelligence.ai/code-review-benchmark-2026)). Supply-chain frontier =
  **SLSA + in-toto attestation** (note: even *valid* SLSA provenance ≠ trust if the build platform misses L3
  isolation — [Legit Security](https://www.legitsecurity.com/blog/slsa-provenance-blog-series-part-2-deeper-dive-into-slsa-provenance)).
- **Long-term agent memory** ★ — **Mem0** (**92.5% LoCoMo, 94.4% LongMemEval, 64.1/48.6 BEAM-1M/10M**, <7K
  tokens/retrieval, −91% p95 latency; independent repro **58–66%**), **Zep/Graphiti** (**63.8% LongMemEval**,
  +18.5% temporal-reasoning gain, −90% latency), **Letta/MemGPT** (leading OSS stateful agent, 13k★), **MemPalace**
  (**88.9% R@10 LoCoMo**, local-first) ([mem0 benchmarks](https://mem0.ai/blog/ai-memory-benchmarks-in-2026),
  [OMEGA leaderboard](https://omegamax.co/benchmarks)).

---

## 2. Capability matrix — purpose-anchored

Cell = capability status for that system. Peers: **MP** meta-pipe · **ARA** · **JE** judge ensembles/MoA ·
**CF** conformal/abstention (CAP/SCOPE/ToolChain-CRC) · **GS** groundedness scorers (HHEM/Cleanlab) · **AF**
agent frameworks (LangGraph/CrewAI/AG2/SDK) · **SG** static gates (semgrep/CodeQL/VibeGuard) · **MEM** memory.

| Dimension (anchored to reproduction-verification) | **Ours** | MP | ARA | JE | CF | GS | AF | SG | MEM |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **Executes** a reproduction (recompute the estimate, not judge text) | 🟢**L** | ✎ | — | — | — | — | — | — | — |
| **Cross-vendor, distinct-family** corroboration of the result | 🟢**L** | — | ✎ | ✎ | — | — | — | — | — |
| **Fail-closed on ambiguity** — abstain, don't *resolve* | 🟢**L** | — | — | ○ | ★ | ○ | — | ✓ | — |
| **Deterministic, model-free** decision core (no LLM in the verdict) | 🟢**L** | — | — | — | ○ | — | — | ✓ | — |
| Verdict **bound to objective witnesses** (tests + numeric-to-tol + R/metafor GT, signed) | 🟢**L** | ○ | — | — | — | — | — | ○ | — |
| **Overclaim / fabrication** linting | 🟢**L** | ✎ | — | — | — | ○ | — | ○ | — |
| **Heterogeneous-vendor multi-PC** execution substrate | 🟢**L** | — | — | — | — | — | ○ | — | — |
| **Conformal / calibrated** abstention | 🟢**L**¹ | — | — | — | ★ | — | — | — | — |
| Semantic/dataflow **static gate** (measured P/R) | ○ | — | — | — | — | — | — | ★ | — |
| Durable **long-term memory** (measured recall) | 🟢**L**² | — | — | — | — | — | ○ | — | ★ |
| **Publicly benchmarked** accuracy number for the task | 🟢**L**³ | — | ★ | ★ | ★ | ★ | ★ | ★ | ★ |

¹ measured (gate engaged, FAR 0.692→0.308) but **empirical, not a formal risk bound** — CF (CAP/SCOPE) still
leads on the *guarantee*. ² LongMemEval_s R@10 **96.4%** / LoCoMo R@10 **45.8%** — competitive on the former,
**behind** on the latter (§4). ³ defect-detection caught 0.9524 / FAR 0.692 raw (0.308 gated) — recall strong,
**FAR poor** (§4).

**Reading it:** the **top seven rows are the truth-gate core; no single peer holds more than two** — only our
column holds all seven (all 🟢**L**). The **bottom four "measurement" rows are now measured** for us — and the
numbers are honestly mixed: strong defect *recall* and LongMemEval retrieval, but poor *false-alarm/precision*
and behind on LoCoMo. Having the number is progress; the number is not uniformly a win (§4).

---

## 3. Depth on the lead dimensions — with honest counter-evidence

### 3a. The defensible moat, stated precisely
> An **execution-based reproduction** corroborated by a **deterministic, model-free consensus-or-flag core**
> across **distinct vendor families**, that **fail-closes on any dissent** (abstain → UNVERIFIED, enforced live
> in `a650361`), **bound to objective witnesses** (R/metafor ≤1e-4, tests, signed CertBundle). No peer combines
> these — verified live today.

### 3b. What is explicitly NOT uniquely ours (de-claiming)
- **Read-from-computation provenance binding** → meta-pipe does it too (parity on mechanism).
- **Overclaim / fabrication linting** → meta-pipe (12 patterns) and semgrep-class tools have analogues.
- **Cross-model corroboration** as a concept → ARA and judge ensembles do it.
- **Abstention** → conformal systems abstain, and with a *formal* guarantee we lack.

### 3c. What cross-vendor actually buys — the recall claim FAILS, the calibration claim HOLDS

This is the uncomfortable finding, stated plainly because the clean measured data demands it.

**The recall-boost claim is not supported.** On the clean two-healthy-vendor run (both vendors 100% usable), the
best single vendor already saturates recall — **agy-only 0.937**, and the heterogeneous panel **C 0.9524** is
only **+1.6pp**. That is not a meaningful "heterogeneous panel boosts recall" effect. It is exactly the case
*Rethinking MoA* ([2502.00674](https://arxiv.org/pdf/2502.00674)) warns about — when one model already dominates,
adding another barely moves the headline metric. **The earlier A/B/C runs that showed a big heterogeneity recall
gain were on a *degraded* agy; with agy healthy the recall gain evaporates.** We must retire the "cross-vendor
lifts recall" framing — the data doesn't support it.

**What the second vendor *does* buy is calibration — and that is real and measured.** The two vendors have
sharply different false-alarm profiles: **agy-only FAR 0.692, Codex-only FAR 0.308** — their errors on the clean
set are *decorrelated*. Flag-on-any-dissent alone can't exploit this (it unions the false alarms → raw C FAR
0.692), but the **conformal gate uses the *disagreement* between the two vendors as the abstention signal**: on a
clean artifact that agy over-flags but Codex passes, the gate abstains. Measured result — **at a matched
false-alarm rate of 0.308, the 2-vendor+gate panel reaches 0.865 recall vs the single best-calibrated vendor
(Codex-only) at 0.786 — a +7.9pp recall gain at equal FAR.** *That* is the cross-vendor payoff on this evidence.

**Restated defensible claim (novelty repositioned honestly):**
> Cross-vendor heterogeneity, on measured evidence, buys **precision/calibration, not recall.** When one vendor
> already saturates recall, a second **error-decorrelated** vendor supplies the disagreement signal a conformal
> gate exploits to suppress the dominant vendor's false alarms — yielding a better recall–false-alarm operating
> point (**+7.9pp recall at matched FAR** vs the best single vendor). This is *precisely* what the co-failure /
> Rethinking-MoA line predicts (a second model helps by decorrelating errors, not by adding capability), applied
> to the false-alarm axis of checkable-result verification.

This is a narrower claim than the original, and correctly so. It concedes the recall point to the frontier
critique and relocates the novelty to calibrated cross-vendor abstention — which the clean data does support.

### 3d. Why the groundedness-scorer numbers still vindicate the design
SOTA text-groundedness (HHEM-2.1 ~**67% F1**) and the finding that **reasoning models hallucinate *more* on
grounded summarization** (>10%, up to 20.2%) show that *scoring text* for faithfulness is inherently lossy. Our
gate sidesteps that class of error by binding "pass" to a **recomputed** number checked against R/metafor — a
stronger primitive than any text-faithfulness score for the quantitative-claims domain. (This is about the
*witness binding*, independent of the cross-vendor recall/calibration question above.)

### 3d. Why the groundedness-scorer numbers vindicate our design
SOTA text-groundedness (HHEM-2.1 ~**67% F1**) and the finding that **reasoning models hallucinate *more* on
grounded summarization** (>10%, up to 20.2%) show that *scoring text* for faithfulness is inherently lossy. Our
gate sidesteps that class of error by binding "pass" to a **recomputed** number checked against R/metafor — a
stronger primitive than any text-faithfulness score for the quantitative-claims domain.

---

## 4. Verdict — lead / parity / lag (purpose-anchored)

**LEAD (verified-live, uniquely ours as a combination):** execution-based reproduction + deterministic,
model-free, fail-closed consensus + objective-witness/R-metafor binding, across heterogeneous vendor nodes — the
7-primitive core block, no peer holds >2, we hold all 7. **Now with a measured number:** defect-detection
**recall 0.9524 [0.900, 0.978]** on a blinded held-out slice. And a **repositioned, narrower** cross-vendor
claim that the clean data *does* support: a decorrelated second vendor + conformal gate buys **calibration**
(+7.9pp recall at matched FAR 0.308) — see §3c.

**PARITY (not ours alone):** read-from-computation provenance binding (meta-pipe); overclaim/fabrication linting
(meta-pipe, semgrep-class); cross-model corroboration as a concept (ARA, judge ensembles); calibrated abstention
as a mechanism (conformal — CF has the formal bound, we have an empirical one). **LongMemEval retrieval:** our
**R@10 96.4%** is competitive with the memory peers' published range (caveat: ours is retrieval-recall@k, several
peer numbers are end-to-end QA accuracy — not strictly apples-to-apples).

**LAG (peers beat us — now with our own numbers making it concrete, not just "unmeasured"):**
- **False-alarm / precision — our weakest axis, now measured and genuinely poor.** Raw C FAR **0.692**; even
  gated **0.308**. Against precision-reporting peers — CodeQL **5% FP**, semgrep **12% FP**, VibeGuard **89.5%
  precision** — a 30–69% false-positive rate is bad. (Caveat: different task + only 13 adversarial cleans; but
  the axis is a real weakness, not an artifact.)
- **LoCoMo memory — measured and behind:** our **R@10 45.8%** vs **MemPalace 88.9% R@10** (same metric,
  ~half). Strong on LongMemEval_s (96.4%), weak on the harder LoCoMo — honestly mixed, net behind on LoCoMo.
- **CAP / SCOPE / ToolChain-CRC** — a *formal* conformal risk bound; ours is empirical (gate engaged this run
  but data-dependent, no coverage guarantee).
- **semgrep / CodeQL / VibeGuard / Qodo** — semantic/dataflow static analysis with measured P/R; Sentinel is
  regex-dominant, still unmeasured.
- **CompassVerifier** — a *trained* verifier; ours is a prompt+regex guard *(mechanism gap)*.
- **LangGraph** — durable checkpoint/time-travel graph; our Dispatch does lease/requeue, not resumable-graph.

**One line (revised, honest):** *We uniquely combine execution-based reproduction with a deterministic,
fail-closed, witness-bound consensus gate, now with a measured blinded defect **recall of 0.9524** and a
repositioned cross-vendor claim (calibration, not recall). But our **false-alarm rate (0.692 raw / 0.308 gated)
is measurably poor** vs precision-reporting peers, and our **LoCoMo memory recall (45.8%) is behind** MemPalace
(88.9%). We can claim best-in-class **recall + architecture** for the reproduction-verification niche; we cannot
yet claim **precision**, and "world's best verifier" remains unearned on the false-alarm axis.*

---

## 5. To credibly claim best-for-purpose, still need — re-ranked (two prior items now DONE)
- ~~Live-vendor accuracy number~~ **DONE** (0.9524 recall, §0). ~~Run LongMemEval/LoCoMo~~ **DONE** (96.4% / 45.8%).
1. **★ FIX FALSE-ALARM / PRECISION — now the single highest-value gap.** 0.692 raw is the number that most
   undercuts a "world-class verifier" claim. Concretely: fix agy's "CI-crosses-1 → direction defect" over-read
   (≈6 of 9 false alarms), require 2-vendor agreement for borderline flags instead of flag-on-any-dissent, and
   add a real per-flag confidence so the conformal gate abstains reliably (not data-dependently).
2. **Close the LoCoMo memory gap** (45.8% → toward MemPalace's 88.9%) — turn/temporal retrieval, not session.
3. **Formal coverage bound for the conformal gate** — so the abstention can stand next to CAP/SCOPE.
4. **Measure Sentinel P/R + move hot rules to AST/semgrep-class.**
5. **A learned-verifier tier (CompassVerifier-class).**

The recall and architecture claims are now earned; the honest headline is bounded by precision, per §4.

---

## 6. Sources & maturity
- **Niche:** [meta-pipe 2606.28363](https://arxiv.org/html/2606.28363),
  [ARA 2605.02651](https://arxiv.org/html/2605.02651v1),
  [ReplicatorBench 2602.11354](https://arxiv.org/html/2602.11354v1).
- **Verification primitives:** [MoA 2406.04692](https://arxiv.org/html/2406.04692v1),
  [PoLL 2404.18796](https://arxiv.org/abs/2404.18796),
  [Rethinking MoA 2502.00674](https://arxiv.org/pdf/2502.00674),
  [When Agents Disagree 2603.20324](https://arxiv.org/pdf/2603.20324),
  [co-failure ceiling 2606.27288](https://arxiv.org/abs/2606.27288),
  [CompassVerifier 2508.03686](https://arxiv.org/abs/2508.03686),
  [CAP PMLR v304](https://proceedings.mlr.press/v304/tayebati26a.html),
  [SCOPE 2602.13110](https://arxiv.org/html/2602.13110v3),
  [ToolChain-CRC 2606.18467](https://arxiv.org/pdf/2606.18467),
  [HHEM-2.1](https://www.vectara.com/blog/hhem-2-1-a-better-hallucination-detection-model),
  [faithfulness leaderboard 2505.04847](https://arxiv.org/html/2505.04847v2).
- **Adjacent stack:** [agentic leaderboard](https://awesomeagents.ai/leaderboards/agentic-ai-benchmarks-leaderboard/),
  [Magentic-One 2411.04468](https://arxiv.org/html/2411.04468v1),
  [framework showdown](https://qubittool.com/blog/ai-agent-framework-comparison-2026),
  [SAST comparison](https://sanj.dev/post/ai-code-security-tools-comparison/),
  [code-review benchmark](https://entelligence.ai/code-review-benchmark-2026),
  [VibeGuard 2604.01052](https://arxiv.org/abs/2604.01052),
  [mem0 benchmarks](https://mem0.ai/blog/ai-memory-benchmarks-in-2026).
- **Maturity caveat:** peer numbers are self-reported upper bounds (independent repro is materially lower — Mem0
  91.6%→58–66%); the reproduction field is immature (best ~43.4%); text-groundedness SOTA is only ~67% F1. Our
  **🟢L** cells were exercised live 2026-07-10; **🟡F** cells are fixture/code-only. No peer system was executed.

*Companion to the frontier scorecard; both score shipped code at `master a650361`. Re-run after the live-eval
pass — several 🟡F cells should become peer-comparable numbers.*
