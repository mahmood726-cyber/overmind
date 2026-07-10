# Peer Benchmark 2026-07-10 — Our Harness vs. Comparable Systems

**Date:** 2026-07-10
**Author:** honest head-to-head (Claude Code / Opus 4.8) for Mahmood
**Scope:** report-only, no code changes, frozen repos untouched. Companion to
[`SYSTEMS-BENCHMARK-2026-07-10.md`](SYSTEMS-BENCHMARK-2026-07-10.md) (our stack vs the research frontier);
this doc puts our harness next to **named, comparable systems** in each category it spans.

**Grounding (verified this pass, not from memory):** `master` HEAD `a650361` — *"harden(orchestrator):
enforce fail-closed consensus in the live judge decision"* (confirmed on `origin/master`); **1277 test
functions** across 132 files (`grep -rho "def test_" | wc -l` = 1277 — matches the claimed count exactly);
the deterministic consensus core is `overmind/review/consensus.py` + `cluster-harness/harness/consensus.py`.

> **Honesty contract.** Peer capabilities are taken from their **papers / READMEs / leaderboards** — I did
> **not** run any peer system. Peer benchmark numbers are self-reported and, per the memory-benchmark
> literature itself, should be read as *upper bounds* (vendors tune to their own harness). Our cells marked
> **🟢L** were exercised live today; **🟡F** are fixture/code-only (proved logic, not live accuracy). No cell
> claims a live number we didn't produce.

---

## 1. Capability matrix — dimensions that matter *for our purpose*

**Legend (per cell):** 🟢**L** present & verified-live (ours) · 🟡**F** present, fixture/code-only (ours) ·
**✓** present & documented (peer) · **★** present & independently/publicly benchmarked (peer) · **○** partial /
buildable-but-not-native · **—** not a design goal / absent.

Peer columns: **LG** LangGraph · **CA** CrewAI/AutoGen(AG2) · **SDK** OpenAI Agents SDK / Claude Agent SDK ·
**JE** judge ensembles / self-consistency / debate · **CF** conformal abstain (CAP / ToolChain-CRC) ·
**PG** pre-commit gates (VibeGuard / semgrep / AI-SAST) · **MEM** memory (Mem0 / Letta / Zep-Graphiti).

| # | Dimension (for our purpose) | **Ours** | LG | CA | SDK | JE | CF | PG | MEM |
|---|---|:---:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| 1 | Cross-**vendor** (distinct-family) consensus | 🟢**L** | — | ○ | — | ✓ | — | — | — |
| 2 | Fail-closed on ambiguity (**abstain**, not resolve) | 🟢**L** | ○ | — | — | ○ | ★ | ✓ | — |
| 3 | **Deterministic, model-free** consensus core | 🟢**L** | — | — | — | — | ○ | ✓ | — |
| 4 | Objective-**witness / provenance** binding (tests+numeric+reproduction, signed) | 🟢**L** | ○ | — | — | — | — | ○ | — |
| 5 | Multi-PC **heterogeneous-vendor** fan-out (SSH/Tailscale) | 🟢**L** | ○ | ○ | — | — | — | — | — |
| 6 | **Conformal / calibrated** abstention (risk bound) | 🟡**F** | — | — | — | ○ | ★ | — | — |
| 7 | **Pre-push static gate** (fabrication + code safety) | 🟢**L** | — | — | — | — | — | ★ | — |
| 8 | Durable **long-term memory** (measured recall) | 🟡**F** | ○ | ○ | ✓ | — | — | — | ★ |
| 9 | Durable / **resumable orchestration graph** (checkpoint) | ○ | ★ | ✓ | ✓ | — | — | — | — |
| 10 | **Publicly measured** quality number | 🟡**F** | ★ | ✓ | ✓ | ★ | ★ | ★ | ★ |

---

## 2. Per-dimension read (who leads + one-line basis)

1. **Cross-vendor consensus — WE LEAD (verified live).** LangGraph/CrewAI/AutoGen are *model-agnostic*
   orchestrators but ship **no distinct-family consensus primitive**; OpenAI SDK is OpenAI-only and Claude SDK
   is Claude-only ([framework showdown](https://qubittool.com/blog/ai-agent-framework-comparison-2026),
   [morphllm SDK reference](https://www.morphllm.com/ai-agent-framework)). Judge-ensembles **do** run
   cross-family panels (e.g. Llama-3.3-70B + Cerebras-GPT-OSS-120B + Qwen3-32B with a meta-judge arbitrator —
   [truth-ensembles gist](https://gist.github.com/bigsnarfdude/21cbae2ef56c01e0f53c223b0e2ca0b1)), so the
   *concept* is not ours alone. Our live round today (Codex+agy, 3 accept / 2 flag correct) is the verified basis.
2. **Fail-closed on ambiguity — WE LEAD *operationally*; CF leads *formally*.** Peer judge panels and debate
   frameworks mostly treat disagreement as a **triage/escalation** signal that *resolves* to an answer (escalate
   to a stronger model — [cross-model disagreement](https://arxiv.org/html/2603.25450);
   [multi-agent debate judges](https://arxiv.org/html/2510.12697v1)). Ours **abstains** (flag-on-any-dissent →
   UNVERIFIED), which is the truth-gate stance. But **CAP** gives a *formal* finite-sample abstention guarantee
   we don't ([CAP, PMLR v304](https://proceedings.mlr.press/v304/tayebati26a.html)).
3. **Deterministic, model-free consensus core — WE LEAD (rare).** Peer arbitration is an **LLM meta-judge**
   (itself fallible/non-deterministic). Ours is deterministic code — `values_agree()` to 1e-9 +
   `extract_number()` — so the *decision* can't hallucinate. Not something the JE/SDK stacks do.
4. **Objective-witness / provenance binding — WE LEAD.** Peers judge free-text quality; ours binds a verdict to
   passing **tests + numerical baselines + reproduction ground-truth**, in a **signed CertBundle** with an
   objective-witness floor. LangGraph offers *tracing* (LangSmith) but not witness-binding; VibeGuard gates
   *artifacts* but not reproduction witnesses.
5. **Multi-PC heterogeneous-vendor fan-out — WE LEAD on the *heterogeneous-vendor-node* variant.** Distributed
   execution exists elsewhere (LangGraph/Ray-style), but running **distinct vendors on distinct physical nodes
   over Tailscale-SSH as the consensus substrate** is ours; verified live today (laptop-Codex + local-agy).
6. **Conformal abstention — CF LEADS.** CAP maintains 90% coverage while improving hallucination-detection AUROC
   +22.2% and cutting calibration error >70% ([CAP](https://proceedings.mlr.press/v304/tayebati26a.html));
   ToolChain-CRC extends risk control to tool-use drift ([2606.18467](https://arxiv.org/pdf/2606.18467)). Ours
   is a **landed gate, fixture-only, no published risk bound** — behind on the formal guarantee.
7. **Pre-push static gate — PG LEADS on mechanism + measurement.** VibeGuard reports **100% recall / 89.5%
   precision** on 8 projects ([2604.01052](https://arxiv.org/abs/2604.01052)); AI-SAST 2026 is
   **semantic/dataflow** ([Augment](https://www.augmentcode.com/guides/what-is-ai-sast)). Sentinel is broader
   in *scope* (64 rules incl. a rare **fabrication/truth-grounding** family) but **42/64 are regex** and it has
   **no published P/R** — parity on breadth, behind on mechanism + measurement.
8. **Durable long-term memory — MEM LEADS on measured recall.** Letta **94.8%**, Mem0 **93.4%**, Zep/Graphiti
   **63.8%** on LongMemEval ([mem0 benchmarks](https://mem0.ai/blog/ai-memory-benchmarks-in-2026),
   [OMEGA leaderboard](https://omegamax.co/benchmarks)). Our store has the *architecture* (temporal validity,
   decay, claim-graph retraction) but **has never been run on LongMemEval** — behind on the number, not the ideas.
9. **Durable resumable orchestration graph — LG LEADS.** LangGraph = checkpoint-at-every-step + time-travel
   ([2026 showdown](https://qubittool.com/blog/ai-agent-framework-comparison-2026)). Our Dispatch has
   **lease/requeue/anti-wedge**, not a resumable graph — a wedged multi-day job restarts a lane, it doesn't
   resume a node. Behind.
10. **Publicly measured quality — MIXED.** Peers post public leaderboard numbers; ours are **fixture evals +
    1277 tests + a private reconstruction corpus (match-or-beat on 7/7 published meta-analyses, R/metafor ≤1e-4)**
    — a *stronger* ground-truth than a public leaderboard, but **not a public-comparable number** and **not
    live-vendor-measured** for consensus accuracy.

---

## 3. Honest verdict — lead / parity / lag

**Where we genuinely lead (the defensible primitive, stated precisely):**
> A **deterministic, model-free consensus-or-flag core** that **fail-closes on *any* cross-vendor dissent**
> (abstain → UNVERIFIED, never majority-rubber-stamp), **bound to objective reproduction witnesses**
> (tests + numerical baselines + a private ground-truth corpus), executed across **heterogeneous vendors on
> distinct physical nodes**, and enforced live in the orchestrator (`master a650361`, verified today).

No peer system combines all five. Judge ensembles have cross-family panels but an **LLM meta-judge** that
*resolves* (not a deterministic core that *abstains*); conformal systems abstain formally but aren't
cross-vendor or witness-bound; orchestrators are model-agnostic but ship **no consensus/truth-gate at all**.
The combination — deterministic + fail-closed + witness-bound + heterogeneous-node — is ours, and it is
**verified-live**, not claimed.

**Where we are at parity (do NOT overclaim):**
- **Cross-model disagreement as a signal** is a well-established 2026 pattern (multi-judge confirmation,
  debate, self-consistency, cross-model-perplexity) — we did **not** invent it
  ([AdversaBench 2606.24589](https://arxiv.org/pdf/2606.24589),
  [sequential-consensus SPRT 2605.19193](https://arxiv.org/pdf/2605.19193)).
- **Distributed execution** and **pre-push gating** as concepts are common.

**Where a peer beats us (named):**
- **LangGraph** — durable checkpoint/time-travel orchestration graph (we have lease/requeue, not resumable graph).
- **CAP / ToolChain-CRC** — formal conformal risk guarantees (ours is a fixture-only gate, no published bound).
- **VibeGuard / AI-SAST / semgrep** — semantic/AST analysis + published precision/recall (Sentinel is
  regex-dominant, unmeasured).
- **Mem0 / Letta / Zep** — published LongMemEval recall 63.8–94.8% (we've never benchmarked memory).
- **CompassVerifier** — a *trained* robust verifier ([2508.03686](https://arxiv.org/abs/2508.03686)); our judge
  is a prompt+regex guard.

**One-line summary:** **LEAD** on the deterministic fail-closed cross-vendor witness-bound consensus primitive
(1 dimension, uniquely ours, verified-live); **PARITY** on 3 (disagreement-signal, distribution, pre-push
concept); **LAG** on 5 (resumable graph, formal conformal bound, semantic static analysis, measured memory
recall, learned verifier) — mostly *measurement* and *mechanism* gaps, not capability-absence.

---

## 4. To credibly claim "best-for-purpose," we still need (tied to the scorecard's open items)

1. **★ Live-eval pass (scorecard #4/adopt-#1).** Publish a **live-vendor** consensus-accuracy number + at least
   one public-comparable figure. Today's live round proves the *mechanism*; it does not yet give an accuracy
   number a peer could compare. This is the single biggest credibility gap.
2. **Run LongMemEval on our store (adopt-#7).** Peers all post a memory recall number; we post none. One run
   converts "architecture parity" into a comparable figure (or exposes a real recall gap).
3. **Measure Sentinel precision/recall (adopt-#5)** against a VibeGuard-style corpus — and move the hot regex
   rules to AST/semantic — so the pre-push claim is measured, not asserted.
4. **State a formal risk bound for the conformal gate (adopt-#3/#4)** — confirm it on live data and report a
   coverage guarantee, so the abstention claim can stand next to CAP's.
5. **A learned-verifier tier (adopt-#2)** — to claim robustness against master-key / token-space judge attacks
   that a regex guard can't fully cover.

Until #1–#2 land, the honest claim is: **"uniquely combines a deterministic fail-closed cross-vendor
witness-bound consensus gate (verified-live), and matches-or-beats on a private reproduction corpus — but is
not yet publicly benchmarked against peers on accuracy or memory recall."** That is defensible and truthful; a
flat "world's best verifier" is not, yet.

---

## 5. Sources & maturity

- **Peer capabilities:** framework comparisons ([QubitTool](https://qubittool.com/blog/ai-agent-framework-comparison-2026),
  [morphllm](https://www.morphllm.com/ai-agent-framework)); judge/consensus
  ([truth-ensembles gist](https://gist.github.com/bigsnarfdude/21cbae2ef56c01e0f53c223b0e2ca0b1),
  [AdversaBench 2606.24589](https://arxiv.org/pdf/2606.24589),
  [debate judges 2510.12697](https://arxiv.org/html/2510.12697v1),
  [cross-model disagreement 2603.25450](https://arxiv.org/html/2603.25450)); conformal
  ([CAP PMLR v304](https://proceedings.mlr.press/v304/tayebati26a.html),
  [ToolChain-CRC 2606.18467](https://arxiv.org/pdf/2606.18467)); pre-commit
  ([VibeGuard 2604.01052](https://arxiv.org/abs/2604.01052),
  [AI-SAST](https://www.augmentcode.com/guides/what-is-ai-sast)); memory
  ([mem0 benchmarks](https://mem0.ai/blog/ai-memory-benchmarks-in-2026),
  [OMEGA leaderboard](https://omegamax.co/benchmarks)); verifier
  ([CompassVerifier 2508.03686](https://arxiv.org/abs/2508.03686)).
- **Maturity caveat:** peer numbers are **self-reported upper bounds** (the memory literature explicitly warns
  that vendors tune to their own harness; re-run on your data before trusting a leaderboard). Our **🟢L** cells
  are verified live 2026-07-10; **🟡F** cells are fixture/code-only. No peer system was executed for this doc.

*Companion to the frontier scorecard; both score shipped code as of 2026-07-10 (`master a650361`). Re-run
after the live-eval pass — several 🟡F cells should become comparable numbers.*
