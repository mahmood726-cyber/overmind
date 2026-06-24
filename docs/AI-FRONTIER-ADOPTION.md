# AI Frontier → Adoption Report

**Date:** 2026-06-24
**Author:** research scan (Claude Code) for Mahmood
**Status:** PROPOSAL — nothing implemented. This is a prioritized plan for your approval.
**Scope:** What recent (≈last 3–6 mo) AI / agentic-engineering work we can adopt into **Sentinel** (pre-push rule engine), **Overmind** (nightly portfolio verifier), the **agent memory system** (markdown facts + SQLite `MemoryStore`), and the **cross-engine verification** layer (engine-pluggable judge).

> **Truth-first caveat.** Items are tagged `[PROD]` (shipped product), `[PREPRINT]` (arXiv, not peer-reviewed), or `[PEER]` (accepted venue). arXiv abstract pages were fetched where possible; a handful of vendor dates/versions come from secondary coverage and are flagged "verify." Do not quote any benchmark number below as fact without checking the primary source. No item here is invented; where credibility is thin it says so.

---

## 0. Our systems as they stand (grounding)

- **Sentinel** (`F:\Sentinel`): pre-push git-hook rule engine. ~57 rules (6 YAML + 51 Python plugins), `Severity = BLOCK/WARN/INFO`, plugin contract = `ID/SEVERITY/SOURCE/SCOPE/check(ctx)`. Findings → `STUCK_FAILURES.jsonl` (BLOCK) / `sentinel-findings.jsonl` (WARN). Bypass = `SENTINEL_BYPASS=1` (tamper-evident hash-chained log). CLI: `scan / list-rules / install-hook / explain / bypass-log`. Portfolio-scope rules run under Overmind.
- **Overmind** (`F:\overmind`): nightly verifier. **TruthCert multi-witness engine** (`test_suite, smoke, semgrep, pip_audit, numerical, numerical_continuity`) → **Arbitrator** → 5-state verdict `CERTIFIED / PASS / UNVERIFIED / REJECT / FAIL`. Risk-tiered witness selection. Signed **CertBundle** (Ed25519 default, HMAC/sigstore fallback). **Engine-pluggable LLM judge** (`OVERMIND_JUDGE_ENGINE`, modes `fallback`|`quorum`; backends claude/codex/agy/gemini/local/stub). **Infra-invariant checker** (force-push-disabled, log health, OAuth expiry, judge-config). **Optional RAG lane** (off by default). Consumes Sentinel JSONL.
- **Memory**: two layers. (a) Markdown facts + `MEMORY.md` index in `…/F--overmind/memory\` (frontmatter `type: user|feedback|project|reference`, `[[wikilinks]]`). (b) Overmind `MemoryStore` (SQLite + FTS5, per-type decay, `valid_from/valid_until`, `source_hash` freshness, embeddings optional).

**Hard constraints any adoption must respect:** force-push stays OFF; truth-first / no fabricated results; no secret-key leakage; cross-engine verification ethos; fail-closed on missing evidence (missing baseline ≠ PASS).

---

## 1. Ranked shortlist (value × effort)

Ranked by **(value ÷ effort), adjusted for fit with our constraints.** "Regression risk" = chance of breaking existing green behavior.

### TIER A — high value, low/medium effort (do first)

#### A1. Harden the LLM judge against degenerate / "master-key" outputs  ★ QUICK WIN (highest value-per-effort)
- **Source:** *One Token to Fool LLM-as-a-Judge* `[PREPRINT]` https://arxiv.org/abs/2507.08794 — bare `:`, a blank, or "Let's solve this step by step." trigger false-positive rewards (punctuation-only up to 35% FPR on GPT-4o; "General Verifier" 66.8% on MATH). Mitigation in paper: a sanitizing reward model ("Master-RM").
- **Where it slots:** `overmind/diagnosis/llm_judge.py` + `judge_backends.py`. Add an input/output sanitizer: reject witness payloads that are empty / whitespace / punctuation-only / a generic filler phrase **before** they can yield a PASS or upgrade an UNKNOWN diagnosis. Treat a degenerate judge response as JUDGE_ERROR, not a low-confidence pass.
- **Why high value:** this is the *exact* mechanism behind our own `SKIP-as-pass` and `placeholder-leak` lessons, generalized. It defends the truth-first ethos directly.
- **Effort:** low (a guard function + 3–4 unit tests). **Regression risk:** very low (only rejects pathological inputs).

#### A2. Decorrelate the cross-engine quorum (measure *effective* votes, enforce different families)
- **Source:** *Nine Judges, Two Effective Votes: Correlated Errors Undermine LLM Evaluation Panels* `[PREPRINT]` https://arxiv.org/abs/2605.29800 (2026-05-28) — a 9-judge panel gave only ~2.2 effective independent votes; correlated failure modes; best single judge ≈ full panel. Counterpoint baseline: *Replacing Judges with Juries (PoLL)* https://arxiv.org/abs/2404.18796 (ensembles of *diverse* small models beat one big judge). Reinforced by self-preference bias work https://arxiv.org/abs/2604.22891 (a model judging same-family output is biased).
- **Where it slots:** `judge_factory.py` quorum mode. (1) Constrain `OVERMIND_JUDGE_MODE=quorum` to engines from **different model families** (claude + gemini + local-qwen ≠ claude + codex if both are GPT-family). (2) Log an "effective independent votes" estimate (agreement-corrected) alongside the nominal count in the bundle. (3) Cheap correctness gate: don't pay for 3 backends when 2 decorrelated ones suffice.
- **Why high value:** we *already ship* quorum mode — this is the documented trap for it. Also caps the ~15× token cost Anthropic reports for multi-agent fan-out (https://www.anthropic.com/engineering/multi-agent-research-system).
- **Effort:** medium. **Regression risk:** low (quorum is opt-in; default is `fallback`).

#### A3. Add CoT + rubric to the judge prompt (bias mitigation that actually works)
- **Source:** *Judging the Judges: Systematic Eval of Bias Mitigation* `[PREPRINT]` https://arxiv.org/abs/2604.23178 (2026-04-25) — **style bias dominates (0.76–0.92), position bias negligible**; chain-of-thought is universally helpful; swap+CoT+rubric gave Claude Sonnet 4 +11.2pp. Position-swapping is model-dependent (helps Gemini, hurts GPT-4o). Also *self-preference mitigation via structured multi-dimensional scoring* https://arxiv.org/abs/2604.22891.
- **Where it slots:** the `DIAGNOSIS_PROMPT` in `llm_judge.py`. Convert the judge to emit explicit reasoning + a small fixed rubric (Relevance/Accuracy/Evidence/Logic) before its verdict; do **not** invest in position-swapping (low payoff here).
- **Effort:** low (prompt + parser change + golden tests). **Regression risk:** low–medium (prompt change → re-run the judge golden set).

#### A4. "Fabricated-artifact / validation-minus-heldout" detection — new truth-first witness + Sentinel rule
- **Source (cluster, all 2026):** *SpecBench* https://arxiv.org/abs/2605.21384 ("reward-hacking gap" = validation pass rate − held-out pass rate); *Reward Hacking Benchmark (tool use)* https://arxiv.org/abs/2605.02964 (most common chained exploit = **"sequence manipulation": fabricating intermediate artifacts to skip expensive upstream work**); *UTBoost* https://arxiv.org/abs/2506.09289 (found **345** SWE-bench patches wrongly marked "passed" → tests passing ≠ task solved).
- **Where it slots:** (a) **Overmind witness** — where a project has both a quick "validation" path and a held-out baseline, compute and record the gap; a large positive gap escalates verdict (REJECT/UNVERIFIED, never CERTIFIED). (b) **Sentinel rule** — `P1-fabricated-artifact`: flag committed "intermediate result" files whose provenance/hash doesn't match a real upstream run (extends the existing `placeholder-leak` / `SKIP-as-pass` family). Note: OpenAI dropped SWE-bench Verified over exactly this kind of contamination (https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/) — validates our held-out-baseline policy.
- **Why high value:** this is our literal threat model (fabricated results gaming the verifier). **Effort:** medium. **Regression risk:** low if it only *escalates*, never auto-passes.

#### A5. Temporal validity on markdown memory facts  ★ QUICK WIN candidate
- **Source:** Zep / **Graphiti** temporal knowledge graph (facts carry validity windows) https://arxiv.org/pdf/2504.19413 (Mem0, related) + Graphiti https://github.com/getzep/graphiti; *A-MEM* Zettelkasten agentic memory https://arxiv.org/abs/2502.12110.
- **Where it slots:** the **markdown** memory layer already mirrors A-MEM (atomic notes + `[[links]]`). Add `valid_from` / `superseded_by` frontmatter (the SQLite `MemoryStore` already has `valid_from/valid_until` — this brings the markdown layer to parity). Directly attacks our recurring **registry-drift / stale-fact** lessons: stale facts decay/flag instead of silently misleading.
- **Effort:** low (frontmatter convention + a lint in the `consolidate-memory` pass). **Regression risk:** none (additive metadata).

### TIER B — high value, higher effort (plan, don't rush)

#### B1. Cross-repo contract-impact verification (the Qodo / CodeRabbit pattern)
- **Source (seed):** *Qodo cross-repo code review* `[PROD beta]` https://thenewstack.io/qodo-cross-repo-code-review/ (2026-06-22) + launch https://www.globenewswire.com/news-release/2026/06/23/3316032/0/en/Qodo-Launches-Governance-Infrastructure-for-the-AI-Coding-Era.html — register consumer repos; on change to a shared dependency/contract, fan out impact findings (signature breaks, schema evolution, infra drift). Also CodeRabbit "linked repos" + live Code Graph https://www.coderabbit.ai/blog/agentic-code-review-vs-rag-multi-repo-analysis ; Greptile codebase graph https://www.greptile.com/agent.
- **Where it slots:** genuinely **new capability**. Overmind verifies each project *independently*; it does not detect when project A breaks project B's contract. Add a portfolio-scope check: when a shared module / fixture / data-schema changes, identify dependent projects and run their witnesses. Natural home: a portfolio-scope **Sentinel** rule feeding an Overmind cross-repo witness.
- **Why high value:** fills a real gap; the whole industry standardized on this pattern in Mar–Jun 2026. **Effort:** high (needs a dependency map across the portfolio). **Regression risk:** medium (new fan-out; scope carefully). **Caution:** CodeRabbit's agentic-vs-RAG argument warns against building this on a *static embedding index* — which validates keeping our RAG lane off-by-default and using live/graph traversal.

#### B2. Runtime groundedness verifier with retraction propagation
- **Source:** *Grounded Continuation: A Linear-Time Runtime Verifier for LLM Conversations* `[PREPRINT]` https://arxiv.org/abs/2605.14175 (2026-05-13) — explicit dependency graph of claim→evidence; groundedness check = a graph walk; **retractions propagate to invalidate dependent conclusions**.
- **Where it slots:** two places. (a) Sentinel `P1-claim-grounding` could move from regex to a claim→source dependency check. (b) The memory `source_hash` freshness mechanism becomes a *graph*: when a source file changes, invalidate all facts (and downstream facts) that depended on it — exactly our "missing premise ⇒ invalidate dependents" lesson, formalized.
- **Effort:** medium–high. **Regression risk:** low (verification-only).

#### B3. Standardize witnesses on Inspect AI (UK AISI)
- **Source:** *Inspect AI* + `inspect_evals` `[PROD, gov-backed]` https://github.com/UKGovernmentBEIS/inspect_evals — MIT, multi-provider, 200+ evals, agentic + OWASP-Agentic-Top-10 coverage. Also eval-as-CI patterns: Braintrust sandboxed scorers + PR-comment regression gates https://www.braintrust.dev/articles/continuous-evaluation-ai-agents-trace-classifications-2026 ; DeepEval pytest integration https://deepeval.com/guides/guides-ai-agent-evaluation.
- **Where it slots:** could replace bespoke judge/eval glue and give us a provider-agnostic witness harness. **Effort:** high (migration). **Regression risk:** medium. Lower-commitment alternative: adopt only the **"production failure → eval case → CI gate"** loop (matches our regression-snapshot rule) without swapping frameworks.

### TIER C — adopt opportunistically / validates current design

#### C1. Cheap label-free cross-model confidence signal (pre-judge filter)
- **Source:** *Cross-Model Disagreement as a Label-Free Correctness Signal* `[PREPRINT]` https://arxiv.org/abs/2603.25450 — a second model's "surprise" (Cross-Model Perplexity) flags errors in one forward pass, no labels. Plus production groundedness scorers: **Vectara HHEM-2.1** https://github.com/vectara/hallucination-leaderboard and **Cleanlab TLM** https://cleanlab.ai/blog/rag-evaluation-models/.
- **Where it slots:** a cheap **first-filter witness** before the expensive LLM judge — only escalate to full cross-engine judging when the cheap signal is uncertain. Cost-tiering. **Effort:** medium. **Regression risk:** low (additive gate).

#### C2. Cost-aware engine routing before dispatch
- **Source:** *One Head, Many Models: Cross-Attention Routing for Cost-Aware LLM Selection* https://arxiv.org/abs/2509.09782 ; *RouteLLM* https://arxiv.org/abs/2406.18665 ; non-frontier verifiers suffice for proofs https://arxiv.org/abs/2604.02450.
- **Where it slots:** `judge_factory.py` engine selection — route cheap/local first, escalate to frontier only on low confidence or verification failure. Complements A2. **Effort:** medium. **Regression risk:** low.

#### C3. Background memory consolidation ("sleep-time compute")
- **Source:** *Sleep-time Compute* https://arxiv.org/abs/2504.13171 + Letta https://www.letta.com/blog/sleep-time-compute — offline passes that merge/dedupe/re-link memory, cutting test-time compute ~5×.
- **Where it slots:** we already have a `consolidate-memory` skill and `MemoryStore.decay_all()`. Formalize a scheduled nightly consolidation (merge duplicates, re-link `[[wikilinks]]`, prune index) — pairs with A5. **Effort:** low–medium. **Regression risk:** low.

#### C4. Reproducible-build / TEE provenance for verdicts (validates our signing)
- **Source:** Reproducible Builds May-2026 report + **Kettle** (verifiable build provenance in a confidential VM) https://reproducible-builds.org/reports/2026-05/ ; **C2PA v2.3** text manifests https://c2pa.org (provenance for LLM text outputs; EU AI Act Art. 50 from 2026-08-02).
- **Where it slots:** our CertBundle already signs with Ed25519 — this is mostly *validation*. Optional: emit a C2PA-style provenance manifest for verdicts as a standards-based complement to HMAC/Ed25519. Kettle's "record source commit + toolchain + artifact digests" is a model if we ever want reproducible verdicts. **Effort:** low (validation) / high (full provenance). **Regression risk:** none.

#### C5. Incremental delta verification (review only what changed)
- **Source:** Cursor BugBot pre-PR `/review` + delta-since-last-run https://www.digitalapplied.com/blog/cursor-bugbot-90-second-reviews-june-2026-release (verify date 2026-06-10, secondary source).
- **Where it slots:** `nightly_verify.py` could skip projects with no source change since their last green verdict (hash-gate), spending the budget on changed/at-risk projects. **Effort:** medium. **Regression risk:** medium (must not skip a project whose *dependency* changed — interacts with B1; be conservative).

#### C6. Design patterns that confirm current architecture (no action, reference)
- Orchestrator-worker + token-cost reality: https://www.anthropic.com/engineering/multi-agent-research-system. Task-ledger/progress-ledger: Magentic https://www.microsoft.com/en-us/research/articles/magentic-one-a-generalist-multi-agent-system-for-solving-complex-tasks/. Context engineering / just-in-time retrieval (= our markdown-index + lazy-read): https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents. Context Rot (don't dump full memory into context): Chroma study (commentary) https://particula.tech/blog/chroma-context-rot-long-context-degradation. Contextual Retrieval (per-fact context line if we ever embed): https://www.anthropic.com/news/contextual-retrieval. Abstention/UNVERIFIED is correct (https://arxiv.org/abs/2604.03904) — we already emit UNVERIFIED.
- Sandboxing landscape (microVM/Firecracker/gVisor + snapshot-restore 5–30ms): https://agentmarketcap.ai/blog/2026/04/07/ai-agent-sandbox-infrastructure-e2b-modal-daytona-fly-machines-secure-code-execution — relevant only if we outgrow multiprocessing-subprocess isolation (not urgent). OPA/Rego policy-as-code https://www.openpolicyagent.org/ — declarative alternative to Sentinel's Python-plugin rules; **high migration cost, would conflict with the current plugin model — not recommended now.**

---

## 2. Quick wins (low effort, high value — start here)

1. **★ A1 — Judge degenerate-output guard.** Reject empty/punctuation-only/filler witness payloads before they can yield PASS. *Single highest value-per-effort item; directly extends our SKIP-as-pass lesson.* (https://arxiv.org/abs/2507.08794)
2. **A5 — Temporal validity frontmatter** (`valid_from`/`superseded_by`) on markdown memory facts → kills registry/stale-fact drift. (Graphiti/Zep, A-MEM)
3. **A3 — CoT + rubric in the judge prompt** (skip position-swapping). (https://arxiv.org/abs/2604.23178)
4. **A2 (partial) — Enforce different-family engines in quorum mode** + log effective-vote estimate. (https://arxiv.org/abs/2605.29800)
5. **C3 — Schedule the existing `consolidate-memory` pass nightly** with dedupe + re-link.

## 3. Constraint / conflict flags

- **A2 (quorum decorrelation)** is *protective* of the cross-engine ethos, not in tension with it — but be honest that nominal 3-engine quorum may be ~2 effective votes; don't market it as "3 independent checks."
- **OPA/Rego migration (C6)** would replace Sentinel's Python-plugin model — high churn, no clear win now. **Do not pursue** unless we want declarative portfolio policy across many machines.
- **B1 cross-repo + C5 delta-skip interact:** never skip a project whose upstream dependency changed. Sequence B1 before/with C5.
- **RAG lane stays off-by-default** — CodeRabbit's agentic-vs-RAG critique (https://www.coderabbit.ai/blog/agentic-code-review-vs-rag-multi-repo-analysis) supports our current default; any cross-repo work should use live/graph traversal, not a static index.
- Nothing here touches force-push (stays off), introduces secret-key exposure, or auto-passes on missing evidence. A4 only *escalates* verdicts; it never relaxes a gate.

## 4. Source credibility notes

- **Strongest / verified primary:** the Anthropic & Microsoft engineering pages, Inspect AI, OpenAI SWE-bench post, Reproducible Builds report, C2PA, Vectara HHEM. Qodo (seed) is a vendor beta + tier-1 trade press (mechanism plausible, unbenchmarked).
- **Preprints (treat as directional, single-lab):** Nine-Judges (A2), Grounded-Continuation (B2), the reward-hacking cluster (A4), bias-mitigation (A3), cross-model-disagreement (C1). Compelling and on-point, but not yet replicated — adopt the *idea*, validate the *numbers* ourselves.
- **Low-credibility (orientation only, not cited for claims):** "best-of-2026" listicles and vendor benchmark win-rates (memory-vendor LongMemEval numbers, framework version tags, CodeRabbit/BugBot exact dates). Verify before quoting.

---

*End of report. Awaiting your pick of which items to implement.*
