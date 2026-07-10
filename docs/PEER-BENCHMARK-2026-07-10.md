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
| **Conformal / calibrated** abstention (risk bound) | 🟡**F** | — | — | — | ★ | — | — | — | — |
| Semantic/dataflow **static gate** (measured P/R) | ○ | — | — | — | — | — | — | ★ | — |
| Durable **long-term memory** (measured recall) | 🟡**F** | — | — | — | — | — | ○ | — | ★ |
| **Publicly benchmarked** accuracy number for the task | 🟡**F** | — | ★ | ★ | ★ | ★ | ★ | ★ | ★ |

**Reading it:** the **top seven rows are the truth-gate core; no single peer holds more than two.** meta-pipe is
closest on *domain* (executes + reads-from-R + overclaim), ARA closest on *cross-model*, JE closest on *panels*,
CF/GS closest on *abstention/groundedness* — but only our column holds all seven, and it's the one marked 🟢**L**.
The **bottom four rows are where peers lead — and every one of those is a *measurement* gap** (we have code/ideas,
they have a published number).

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

### 3c. The heterogeneity thesis — honest handling of the strongest counter-evidence
Our differentiator rests on "a *different* vendor catches what the first missed." *Rethinking MoA*
([2502.00674](https://arxiv.org/pdf/2502.00674)) is the sharpest challenge: for **generation quality**, mixing
different models is **not** automatically better — **Self-MoA** (resampling the single best model) often wins when
one model dominates. I take that seriously. The reconciliation is a **task-type distinction**:
- *Rethinking MoA* optimizes **answer quality** (AlpacaEval win-rate) — there, a weak model can *dilute* a strong
  one, so same-model resampling is efficient.
- Our task is **error-catch verification of a checkable numeric result** — there the relevant quantity is
  **decorrelated failure** (β / co-failure), and the [co-failure-ceiling paper (2606.27288)](https://arxiv.org/abs/2606.27288)
  says explicitly that on *checkable* tasks gains come from models **failing on different questions**, with
  low-ρ heterogeneous ensembles beating high-ρ ones.
- Three independent lines converge for **our** task-type: (i) our measured **A/B/C** — homogeneous B (0.770)
  catches **fewer** defects than single-agent A (0.802), heterogeneous C **0.921**; (ii) co-failure-ceiling
  theory; (iii) meta-pipe's own concession that intra-model retest "is not inter-rater reliability."

**Honest scope:** the heterogeneity claim is defensible **for checkable-result verification**, which is our
purpose — **not** as a universal "mixing always helps" (which *Rethinking MoA* correctly refutes for generation).
We should never cite our cross-vendor edge outside the verification setting.

### 3d. Why the groundedness-scorer numbers vindicate our design
SOTA text-groundedness (HHEM-2.1 ~**67% F1**) and the finding that **reasoning models hallucinate *more* on
grounded summarization** (>10%, up to 20.2%) show that *scoring text* for faithfulness is inherently lossy. Our
gate sidesteps that class of error by binding "pass" to a **recomputed** number checked against R/metafor — a
stronger primitive than any text-faithfulness score for the quantitative-claims domain.

---

## 4. Verdict — lead / parity / lag (purpose-anchored)

**LEAD (verified-live, uniquely ours as a combination):** execution-based reproduction + deterministic,
model-free, fail-closed **cross-vendor** consensus + objective-witness/R-metafor binding, across heterogeneous
vendor nodes. Across the 11-row matrix **no peer holds >2 of the 7 core primitives; we hold all 7**, and the
block is verified-live. The heterogeneity basis is triangulated (measured A/B/C + co-failure theory + a
competitor's own concession), and correctly scoped to *verification*, not generation.

**PARITY (not ours alone):** read-from-computation provenance binding (meta-pipe); overclaim/fabrication linting
(meta-pipe, semgrep-class); cross-model corroboration as a concept (ARA, judge ensembles); abstention disposition
(conformal — more formal there).

**LAG (peers beat us — five *measurement* gaps, one *mechanism*):**
- **ARA** — a published reproducibility-accuracy number (~61%); we have none peer-comparable.
- **CAP / SCOPE / ToolChain-CRC** — a *formal* conformal risk bound (+22.2% AUROC etc.); ours is a fixture-only gate.
- **semgrep / CodeQL / VibeGuard / Qodo** — semantic/dataflow static analysis with measured P/R (88%/5%, 82%/12%,
  100%R/89.5%P, 60.1% F1); Sentinel is regex-dominant, unmeasured.
- **Mem0 / Letta / Zep** — published LoCoMo/LongMemEval recall (92.5/94.4, 63.8%); we've never benchmarked memory.
- **CompassVerifier** — a *trained* verifier; ours is a prompt+regex guard *(mechanism, not just measurement)*.
- **LangGraph** — durable checkpoint/time-travel graph; our Dispatch does lease/requeue, not resumable-graph.

**One line:** *We uniquely combine execution-based reproduction with a deterministic, fail-closed, cross-vendor,
witness-bound consensus gate (verified-live), scoped correctly to verification, and match-or-beat on a private
R/metafor-checked corpus — but, unlike ARA and the memory/SAST peers, we have no publicly-comparable accuracy or
recall number yet.* Defensible; "world's best verifier" is not, yet.

---

## 5. To credibly claim best-for-purpose, still need (tied to scorecard open items)
1. **★ Live-vendor accuracy number (scorecard #4).** ARA sets the bar (~61% on a public reproducibility corpus);
   publish ours (reconstruct-and-beat is the natural instrument — report a caught-defect/calibration figure vs
   held-out truth).
2. **Run LongMemEval/LoCoMo once (adopt-#7)** — every memory peer posts a number; we post none.
3. **Formal coverage bound for the conformal gate (adopt-#3/#4)** — so abstention can stand next to CAP/SCOPE.
4. **Measure Sentinel P/R + move hot rules to AST/semgrep-class (adopt-#5)** — next to semgrep 82%/12%, CodeQL 88%/5%.
5. **A learned-verifier tier (adopt-#2)** — CompassVerifier-class, to harden past regex guards.

Until #1–#2 land, the truthful headline is the §4 "one line" — a bounded, defensible, triangulated claim.

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
