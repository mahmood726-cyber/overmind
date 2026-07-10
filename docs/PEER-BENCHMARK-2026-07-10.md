# Peer Benchmark 2026-07-10 — Our Harness vs. Comparable Systems

**Date:** 2026-07-10 · **report-only, no code changes, frozen repos untouched.**
Companion to [`SYSTEMS-BENCHMARK-2026-07-10.md`](SYSTEMS-BENCHMARK-2026-07-10.md) (us vs the research
frontier). This doc is a proper head-to-head against **named, comparable systems**, judged **only** on what
matters for our purpose.

**The purpose everything is judged against (anchor — do not drift):** *a truth-gated, heterogeneous-vendor
**reproduction-and-verification** orchestrator for quantitative **evidence-synthesis** — reproduce a pooled
estimate from open data, cross-check it across **independent vendors**, bind the verdict to **objective
witnesses**, and **flag/abstain** rather than emit a wrong "pass."* Generic agent-framework features (handoffs,
streaming, tool ergonomics) are scored only where they bear on that job.

**Grounding (verified this pass, not memory):** `master` HEAD `a650361` ("enforce fail-closed consensus in the
live judge decision", confirmed on `origin/master`); **1277 test functions** (`grep -rho "def test_"` = 1277,
exact match); deterministic consensus core = `overmind/review/consensus.py` + `cluster-harness/harness/consensus.py`;
the reproduction eval = `evals/reconstruct_and_beat.py` (7/7 published meta-analyses reconstructed, cross-checked
to R/metafor ≤1e-4).

> **Honesty labels (used throughout).** 🟢**L** verified-live today · 🟡**F** ours, fixture/code-only (logic
> proven, not live-vendor accuracy) · **★** peer, **publicly benchmarked** (number cited) · **✎** peer,
> **paper/README-claimed** (not re-run by me) · **—** not a design goal / absent. **No peer system was executed
> for this doc**; every peer number is self-reported and should be read as an *upper bound* (vendors tune to
> their own harness — the memory-benchmark literature says so explicitly).

---

## 1. The peer landscape, ranked by relevance to our purpose

### Tier 1 — direct niche peers (automated evidence-synthesis reproduction/verification)

These are the systems that actually share our job. They matter most, and being fair to them **narrows** our
lead claim.

- **meta-pipe** ✎ ([arXiv 2606.28363](https://arxiv.org/html/2606.28363)) — an LLM-agent pipeline for the full
  systematic-review/meta-analysis workflow (search→screen→extract→analyze→manuscript), **built on the same R
  stack we use** (`meta`, `metafor`, `gemtc`, `netmeta`) + Claude (Opus 4 / Haiku 3.5), 10 stages, 5 human
  decision points. Crucially it **already does two things I might have claimed as ours**: (a) **overclaim
  detection** (12 unsupported-claim patterns — a Sentinel-fabrication-family analogue), and (b) **reads effect
  estimates directly from R output files to prevent hallucination of statistics** — our numerical-fidelity /
  witness-binding idea. **But:** it is **single-model (Claude only; portability "not tested")**, **generative
  not a verifier** ("this is a system description, not a validation study; no validation data are reported"),
  and its "test-retest" reliability is **two passes of the *same* model** — the authors explicitly note this
  "measures intra-model stability rather than inter-rater reliability." That concession is an **independent
  corroboration of our core thesis** (why a homogeneous panel doesn't verify; you need *different* vendors).
- **ARA — Agentic Reproducibility Assessment** ★ ([arXiv 2605.02651](https://arxiv.org/html/2605.02651v1)) —
  turns a paper into a workflow graph and scores **reconstructability from the text**. It **is cross-model**
  (Gemini/GPT-4/Qwen, for assessment robustness) and **publicly benchmarked**: **60.98%** on ReScience C,
  **60.71%** ReproBench (vs 36.84% ReplicatorAgent), **61.68%** GoldStandardDB (vs 43.56% ReproScreener).
  **But:** it is **document-level only — it does not execute or reproduce anything**, so it can't bind to
  objective run witnesses and (its own caveat) is "systematically optimistic."
- **Reproduction benchmarks** ✎ — CORE-Bench, PaperBench, REPRO-Bench, ReplicatorBench
  ([2602.11354](https://arxiv.org/html/2602.11354v1)); best model averages only **~43.4%** replication — the
  field is real but immature, which is context for how hard our job is.

### Tier 2 — verification primitives we compose

- **Judge ensembles / self-consistency / debate** ✎/★ — cross-family judge panels exist in practice (e.g.
  Llama-3.3-70B + Cerebras-GPT-OSS-120B + Qwen3-32B with a meta-judge —
  [truth-ensembles](https://gist.github.com/bigsnarfdude/21cbae2ef56c01e0f53c223b0e2ca0b1)); debate-as-judge and
  cross-model disagreement-as-signal are staples ([2510.12697](https://arxiv.org/html/2510.12697v1),
  [2603.25450](https://arxiv.org/html/2603.25450)). The **co-failure-ceiling** result bounds them
  ([2606.27288](https://arxiv.org/abs/2606.27288)).
- **CompassVerifier** ★ ([2508.03686](https://arxiv.org/abs/2508.03686), EMNLP 2025) — a **trained** robust
  verifier / reward model (the learned-verifier tier we lack).
- **Conformal abstain — CAP / ToolChain-CRC** ★ — formal, finite-sample abstention with a risk bound (CAP: 90%
  coverage, +22.2% hallucination-AUROC, >70% lower calibration error —
  [PMLR v304](https://proceedings.mlr.press/v304/tayebati26a.html); [2606.18467](https://arxiv.org/pdf/2606.18467)).

### Tier 3 — adjacent stack (orchestration / static-gate / memory)

- **Agent frameworks** ✎ — LangGraph (durable checkpoint + time-travel), CrewAI (role crews), **AG2/AutoGen**
  (GroupChat, 9 orchestration patterns, conversational multi-agent *consensus by debate*; note MS AutoGen is now
  maintenance-mode, AG2 is the community fork), OpenAI Agents SDK (handoffs, OpenAI-only), Claude Agent SDK
  (subagents, Claude-only) ([showdown](https://qubittool.com/blog/ai-agent-framework-comparison-2026)). LangGraph
  et al. are model-agnostic **orchestrators**; none ship a truth-gate primitive — AG2's GroupChat "consensus" is
  *LLM agents agreeing in conversation*, not a deterministic, fail-closed gate.
- **Static gates** ★ — **semgrep** (AST rules that look like source; AppSec adds cross-file data-flow → −25% FP /
  +250% TP; **82% acc / 12% FP**; median 10s CI), **CodeQL** (deepest dataflow; **88% acc / 5% FP**), **VibeGuard**
  (AI-code gate, **100% R / 89.5% P** on 8 projects — [2604.01052](https://arxiv.org/abs/2604.01052))
  ([SAST comparison](https://sanj.dev/post/ai-code-security-tools-comparison/)).
- **Memory** ★ — Mem0 **93.4%**, Letta **94.8%**, Zep/Graphiti **63.8%** on LongMemEval
  ([mem0 benchmarks](https://mem0.ai/blog/ai-memory-benchmarks-in-2026)).

---

## 2. Capability matrix — purpose-anchored

Rows = the primitives our purpose demands. Columns = **Ours** and the peers that plausibly compete on that row
(meta-pipe **MP**, ARA, judge-ensembles **JE**, conformal **CF**, agent-frameworks **AF**, static-gate **SG**,
memory **MEM**). Cell = capability status for that system.

| Dimension (anchored to reproduction-verification) | **Ours** | MP | ARA | JE | CF | AF | SG | MEM |
|---|:---:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **Executes** a reproduction (recompute the estimate, not judge text) | 🟢**L** | ✎ | — | — | — | — | — | — |
| **Cross-vendor, distinct-family** corroboration of the result | 🟢**L** | — | ✎ | ✎ | — | — | — | — |
| **Fail-closed on ambiguity** — abstain, don't *resolve* to an answer | 🟢**L** | — | — | ○ | ★ | — | ✓ | — |
| **Deterministic, model-free** decision core (no LLM in the verdict) | 🟢**L** | — | — | — | ○ | — | ✓ | — |
| Verdict **bound to objective witnesses** (tests + numeric-to-tolerance + R/metafor ground-truth, signed) | 🟢**L** | ○ | — | — | — | — | ○ | — |
| **Overclaim / fabrication** linting | 🟢**L** | ✎ | — | — | — | — | ○ | — |
| **Heterogeneous-vendor multi-PC** execution substrate | 🟢**L** | — | — | — | — | ○ | — | — |
| **Conformal / calibrated** abstention (risk bound) | 🟡**F** | — | — | — | ★ | — | — | — |
| Semantic/dataflow **static gate** (measured P/R) | ○ | — | — | — | — | — | ★ | — |
| Durable **long-term memory** (measured recall) | 🟡**F** | — | — | — | — | ○ | — | ★ |
| **Publicly benchmarked** accuracy number | 🟡**F** | — | ★ | ★ | ★ | ★ | ★ | ★ |

Reading the matrix: **the top seven rows are the truth-gate core, and no single peer holds more than two of
them.** meta-pipe is closest on *domain* (executes reproduction, has overclaim linting, reads-from-R witness
binding) but is single-vendor with no consensus gate; ARA is closest on *cross-model* but doesn't execute.
Nobody but us holds the whole top block — and it's the one column marked 🟢**L**.

---

## 3. Depth on the dimensions where we lead — with honest overlap

### 3a. The unique *combination* (the defensible moat), stated precisely
> An **execution-based reproduction** whose result is corroborated by a **deterministic, model-free
> consensus-or-flag core** across **distinct vendor families**, that **fail-closes on any dissent** (abstain →
> UNVERIFIED, enforced live in the orchestrator `a650361`), **bound to objective witnesses** (R/metafor
> ground-truth to ≤1e-4, tests, signed CertBundle).

**No peer combines these.** meta-pipe executes + binds-to-R + lints overclaims **but is single-model and
generative** (no cross-vendor gate, no validation); ARA is cross-model **but doesn't execute and isn't a gate**;
judge ensembles are cross-family **but arbitrate with an LLM meta-judge that *resolves* rather than abstains**;
conformal abstains formally **but isn't cross-vendor or reproduction-bound**; agent frameworks ship **no
truth-gate at all**. Verified live today: a real Codex+agy+deterministic round — 3 agreements ACCEPTED, 2 seeded
disagreements FLAGGED, a 2-agree/1-conflict panel correctly FLAGGED (flag-on-any-dissent, not majority-vote).

### 3b. What is NOT uniquely ours (honest de-claiming)
- **Provenance / read-from-computation binding** — **meta-pipe does this too** (reads effect estimates from R
  output to prevent hallucination). We are at **parity** on the mechanism; our edge is that ours is *cross-vendor
  and gated*, not single-model and generative.
- **Overclaim / fabrication detection** — **meta-pipe (12 patterns) and semgrep-class tools** have analogues.
  Sentinel's fabrication family is broader and truth-domain-specific, but the *idea* is shared.
- **Cross-model corroboration** — **ARA and judge ensembles** do it. Ours is distinguished by being
  *deterministic + fail-closed + reproduction-bound*, not by being cross-model per se.

### 3c. The one thing our own data proves that the field is still arguing about
The **heterogeneity thesis** — that a *same-vendor* panel doesn't verify, you need *different* vendors — is (i)
our measured A/B/C result (homogeneous B 0.770 catches **fewer** defects than single-agent A 0.802; heterogeneous
C **0.921**), (ii) the co-failure-ceiling theory ([2606.27288](https://arxiv.org/abs/2606.27288)), **and** (iii)
independently conceded by meta-pipe ("intra-model stability, not inter-rater reliability"). Three independent
lines agreeing is a genuinely strong, defensible position — and it's the reason our differentiator is
*cross-vendor*, not *more-votes*.

---

## 4. Verdict — lead / parity / lag (purpose-anchored)

**LEAD (verified-live, uniquely ours as a combination):** execution-based reproduction + deterministic,
model-free, fail-closed **cross-vendor** consensus + objective-witness/R-metafor binding, running across
heterogeneous vendor nodes. No Tier-1/2/3 peer holds more than two of these seven core primitives; we hold all
seven, and the block is verified-live.

**PARITY (explicitly not ours alone):**
- read-from-computation **provenance binding** (meta-pipe),
- **overclaim/fabrication** linting (meta-pipe, semgrep-class),
- **cross-model corroboration** as a concept (ARA, judge ensembles),
- **abstention disposition** (conformal systems abstain too — and more formally).

**LAG (peers beat us — mostly *measurement*, one *mechanism*):**
- **ARA** — a **published reproducibility-accuracy number** (~61%); we have none that's peer-comparable.
- **CAP / ToolChain-CRC** — a **formal conformal risk bound**; ours is a fixture-only gate.
- **semgrep / CodeQL / VibeGuard** — **semantic/dataflow static analysis with measured P/R** (88%/5%, 82%/12%,
  100%R/89.5%P); Sentinel is regex-dominant and unmeasured.
- **Mem0 / Letta / Zep** — **published LongMemEval recall** (93.4/94.8/63.8%); we've never benchmarked memory.
- **CompassVerifier** — a **trained** robust verifier; ours is a prompt+regex guard.
- **LangGraph** — durable checkpoint/time-travel graph; our Dispatch does lease/requeue, not resumable-graph.

**One line:** *We uniquely combine execution-based reproduction with a deterministic, fail-closed, cross-vendor,
witness-bound consensus gate (verified-live), and match-or-beat on a private R/metafor-checked corpus — but,
unlike ARA and the memory/SAST peers, we have no publicly-comparable accuracy or recall number yet.* That is the
defensible claim; "world's best verifier" is not, yet.

---

## 5. To credibly claim best-for-purpose, still need (tied to scorecard open items)

1. **★ Live-vendor accuracy number (scorecard #4).** Today proved the *mechanism*, not accuracy — and ARA shows
   the bar: a peer-comparable number on a reproducibility corpus. Publish ours (reconstruct-and-beat is the
   natural instrument; report a caught-defect / calibration figure against held-out truth).
2. **Run LongMemEval once (adopt-#7).** Every memory peer posts a number; we post none.
3. **Formal coverage bound for the conformal gate (adopt-#3/#4)** — so abstention can stand next to CAP.
4. **Measure Sentinel P/R + move hot rules to AST/semgrep-class (adopt-#5)** — so the static-gate claim can sit
   next to semgrep's 82%/12% and CodeQL's 88%/5%.
5. **A learned-verifier tier (adopt-#2)** — CompassVerifier-class, to harden the judge past regex guards.

Until #1–#2 land, the truthful headline is the "one line" in §4 — a bounded, defensible claim, not a
leaderboard boast.

---

## 6. Sources & maturity
- **Direct niche:** [meta-pipe 2606.28363](https://arxiv.org/html/2606.28363),
  [ARA 2605.02651](https://arxiv.org/html/2605.02651v1),
  [ReplicatorBench 2602.11354](https://arxiv.org/html/2602.11354v1).
- **Verification primitives:** [CompassVerifier 2508.03686](https://arxiv.org/abs/2508.03686),
  [truth-ensembles](https://gist.github.com/bigsnarfdude/21cbae2ef56c01e0f53c223b0e2ca0b1),
  [debate judges 2510.12697](https://arxiv.org/html/2510.12697v1),
  [co-failure ceiling 2606.27288](https://arxiv.org/abs/2606.27288),
  [CAP PMLR v304](https://proceedings.mlr.press/v304/tayebati26a.html),
  [ToolChain-CRC 2606.18467](https://arxiv.org/pdf/2606.18467).
- **Adjacent stack:** [framework showdown](https://qubittool.com/blog/ai-agent-framework-comparison-2026),
  [SAST comparison](https://sanj.dev/post/ai-code-security-tools-comparison/),
  [VibeGuard 2604.01052](https://arxiv.org/abs/2604.01052),
  [mem0 benchmarks](https://mem0.ai/blog/ai-memory-benchmarks-in-2026).
- **Maturity caveat:** peer numbers are self-reported upper bounds (re-run on our data before trusting any);
  meta-pipe and the reproduction field are largely **unvalidated/immature** (best replication ~43.4%). Our
  **🟢L** cells were exercised live 2026-07-10; **🟡F** cells are fixture/code-only. No peer system was executed.

*Companion to the frontier scorecard; both score shipped code at `master a650361`. Re-run after the live-eval
pass — several 🟡F cells should become peer-comparable numbers.*
