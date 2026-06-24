# Systems Benchmark — Our Stack vs. the AI-Engineering Frontier

**Date:** 2026-06-24
**Author:** evidence-grounded benchmark (Claude Code) for Mahmood
**Method:** read our actual code (the `overmind`, `Sentinel`, `Beast` repos + agent memory) + the
[AI-FRONTIER-ADOPTION.md](AI-FRONTIER-ADOPTION.md) survey, then web-searched current (mid-2026)
public agentic-engineering work. Every "ahead/parity/behind" call is justified against **what our
code does today**, not what it aspires to.

> **Truth-first contract.** No flattery. Where our advantage is real it's marked real; where it is
> asserted-by-construction-but-never-measured, it says so; where a claimed capability does not exist
> in code, it is flagged as **aspirational**. Frontier sources are linked with maturity tags
> `[PROD]` / `[PREPRINT]` / `[GOV/OSS]`. Preprint numbers are directional, not gospel.

---

## 0. The single most important honesty flag (read first)

**The "multi-node Tailscale cluster" does not exist in any readable form.** A full-text search across
the `overmind`, `Beast`, `Sentinel` repos, the Claude config dir (`~/.claude/`: CLAUDE.md, AGENTS.md,
LIVE_CONTEXT.md, rules/) and the agent memory dir for `tailscale | cluster | multi-node | worker |
distributed | remote runner | fleet` returned **no topology, no node count, no deploy script, no
remote-runner code**. Overmind today is a **single-process, single-machine, sequential nightly
verifier** (`overmind/core/orchestrator.py` is one `Orchestrator`; `overmind/runners/` holds only
local CLI runner plugins). Beast is likewise single-process.

So the "Scalability / cluster" dimension below is benchmarked honestly: **what we ship is
single-node**; the cluster is a plan, and is scored as such. If cluster docs/infra exist outside
these repos, they were not available to this benchmark and none of the scoring credits them.

---

## 1. Scorecard (dimension → verdict)

| # | Dimension | Verdict | One-line justification |
|---|-----------|---------|------------------------|
| 1 | Orchestration & routing | **BEHIND** (parity within narrow scope) | Solid single-node verification pipeline; no durable graph orchestration, no cost-aware routing. |
| 2 | Verification / judging robustness | **PARITY → slightly AHEAD (discipline)**; BEHIND on learned verifiers | Degenerate-guard + CoT-rubric + abstention are frontier-grade *discipline*; we use heuristics, not a trained robust reward model. |
| 3 | Memory & knowledge management | **PARITY** (BEHIND on graph + measured quality) | Temporal-validity + decay + consolidation = frontier ideas, implemented; no entity graph, never benchmarked. |
| 4 | Evaluation / benchmarking discipline | **BEHIND** | Real regression/baseline discipline, but bespoke witnesses; no standardized harness, no held-out scores — incl. zero score on **SpecBench**, the canonical external measure of our exact threat. |
| 5 | Truth-recovery / groundedness | **AHEAD (operational)**; PARITY on formal groundedness | Fail-closed + UNVERIFIED + fabrication rules beat typical practice; no claim→evidence retraction graph. |
| 6 | Multi-engine cross-checking | **AHEAD** | Genuine cross-*family* quorum with effective-vote decorrelation — rare in production. |
| 7 | Sandboxing / safety | **MIXED** (AHEAD on policy invariants, BEHIND on execution isolation) | Strong force-push/OAuth/bypass-audit invariants; witness code runs as host subprocesses, not microVMs. |
| 8 | Observability | **PARITY** (BEHIND on tracing) | Good metrics/JSONL/signed bundles; no span-level distributed tracing. |
| 9 | Scalability (the cluster) | **BEHIND** | Single-machine sequential nightly. The cluster is **aspirational/undocumented**. |
| 10 | Reproducibility | **AHEAD** | Signed bundles + immutable scope-lock + numerical baselines + deterministic indexing. |

**Tally:** 2 clearly AHEAD (6, 10), 1 AHEAD-operational (5), 3 PARITY (2, 3, 8), 3 BEHIND (1, 4, 9),
1 MIXED (7).

---

## 2. Per-dimension assessment

### 1. Orchestration & routing — **BEHIND (parity within narrow scope)**

**What we do (code):** `overmind/core/orchestrator.py` runs a deterministic verify pipeline;
`overmind/runners/` provides local CLI runner plugins (Claude / Codex / Gemini). The judge layer has
real engine selection (`judge_factory.build_judge`, `fallback` vs `quorum`,
`OVERMIND_JUDGE_ENGINE` default `claude,gemini`).

**Frontier:** OpenAI Agents SDK (handoffs), Google ADK, the Claude Agent SDK (hooks/MCP/skills/
subagents, one level deep), and LangGraph (durable, model-agnostic graph control plane) converge on
the **supervisor topology** as the 2026 production default; framework choice alone moves agent
benchmark scores by up to ~30pp on identical models. [PROD/OSS]
([frameworks survey](https://www.morphllm.com/ai-agent-framework),
[orchestration patterns](https://www.digitalapplied.com/blog/multi-agent-orchestration-5-patterns-that-work))

**Honest gap:** We have no durable/resumable graph engine, no human-in-the-loop checkpointing, and
**no cost-aware routing** (RouteLLM-style escalation, our own deferred item C2). For our *actual job*
— a deterministic nightly verifier — a full agent-graph framework would be over-engineering, so
this is "behind on general orchestration, adequate for the domain." But the missing piece that
*would* help us is cheap engine routing (cheap/local first, escalate on low confidence).

### 2. Verification / judging robustness — **PARITY → slightly AHEAD on discipline; BEHIND on learned verifiers**

**What we do (code):** `verification/llm_judge.py` requires an explicit `VERDICT:` line
(`_parse_verdict`, ~L318) and now ships a **degenerate-output guard** (`degenerate_response_reason`,
~L424): empty / whitespace / punctuation-only / generic-filler-without-verdict replies return
`passed=False, concerns=["judge_error","judge_degenerate"]` — they can never yield PASS. The
**CoT+rubric** prompt (`JUDGE_PROMPT_TEMPLATE_COT`, ~L214; `_cot_enabled`) adds a
Relevance/Accuracy/Evidence/Logic rubric (opt-in, default OFF). The arbitrator emits a 5-state
verdict including **UNVERIFIED** (all-pass but numerical baseline missing) — i.e. principled
abstention.

**Frontier:** This directly tracks the live research:
- *One Token to Fool LLM-as-a-Judge* [PREPRINT] — punctuation/filler "master keys" fool GPT-4o,
  o1, Claude-4; mitigation = a sanitizing reward model. We implement the **guard** version of this.
  ([arXiv 2507.08794](https://arxiv.org/abs/2507.08794))
- *RobustJudge* and a *Security SoK for LLM-as-a-Judge* show judges are broadly attackable; the
  defended state of the art is **trained robust verifiers** — CompassVerifier, Master-RM,
  reasoning-based judges. [PREPRINT]
  ([CompassVerifier](https://arxiv.org/pdf/2508.03686),
  [Security SoK](https://arxiv.org/pdf/2603.29403),
  [Explicit Reasoning Makes Better Judges](https://arxiv.org/pdf/2509.13332))
- Bias-mitigation systematic study: CoT universally helps, style-bias dominates, position-bias
  negligible — which is **exactly** why our CoT prompt deliberately skips position-swapping. [PREPRINT]
  ([arXiv 2604.23178](https://arxiv.org/abs/2604.23178))

**Honest call:** Our *operational discipline* (guard + abstention + never-pass-on-missing-evidence)
is at or slightly ahead of typical LLM-judge deployments, and it is grounded in the same papers the
frontier cites. But we do **not** train a robust reward model; we use prompt + heuristic guards.
CompassVerifier/Master-RM-class learned verifiers are more robust under adversarial pressure than a
regex guard. So: ahead on *discipline*, behind on *learned-verifier sophistication*. We have also
**never measured** our judge's false-positive rate on a master-key adversarial set — see Dimension 4.

### 3. Memory & knowledge management — **PARITY (BEHIND on graph + measured quality)**

**What we do (code):** Two layers. (a) SQLite+FTS5 `MemoryStore` (`memory/store.py`,
`storage/db.py`) with per-type **decay** (feedback/user 0.99 … bundle_failure 0.85), **temporal
validity** (`valid_from`/`valid_until`, `supersede`, `expire_memories`), **source_hash freshness**
(`is_stale` recomputes hash → "memory ≠ evidence"), and **optional lazy embeddings** (MiniLM,
graceful FTS5 fallback). (b) Markdown facts + `MEMORY.md` index (`memory/file_index.py`) with
BM25 ranking, `[[wikilink]]` graph, and now **temporal frontmatter** (`is_current`,
`superseded_by`). `dream_engine.py` does scheduled consolidation: expire → extract heuristics →
failure-cluster → merge-duplicates (≥60% title overlap) → prune (<0.1 relevance). A nightly
Task-Scheduler job runs the deterministic decay pass.

**Frontier:** The four-vendor memory market (Letta/MemGPT, Zep/Graphiti, Mem0, LangMem). Zep's
**Graphiti** stores facts in a **temporal knowledge graph** with validity windows and scores
**63.8% on LongMemEval** (GPT-4o) vs Mem0's 49.0% — a 15pt gap on exactly the change-over-time
capability. A-MEM's Zettelkasten (atomic notes + links) and "sleep-time compute" (offline
consolidation cutting test-time compute ~5×) are the academic roots. [PROD/PREPRINT]
([memory vendor landscape](https://agentmarketcap.ai/blog/2026/04/10/agent-memory-vendor-landscape-2026-letta-zep-mem0-langmem),
[frameworks tested](https://particula.tech/blog/agent-memory-frameworks-tested-mem0-zep-letta-cognee-2026))

**Honest call:** Our **architecture** is genuinely frontier-aligned — temporal validity, decay,
source-freshness, and consolidation are precisely the ideas Zep/A-MEM/sleep-time-compute promote,
and we implemented them in working code (the markdown + SQLite split mirrors the
"buy memory at the edges, build core internally" hybrid 65% of enterprises use). **Two real gaps:**
(1) we have **no entity-relationship graph** — Graphiti reasons over a typed temporal graph; we have
wikilinks + FTS5/BM25, which is shallower; (2) we have **never run LongMemEval or any retrieval
benchmark** against our store, so "good retrieval" is asserted, not measured. Parity on ideas,
unmeasured on quality, behind on graph reasoning.

### 4. Evaluation / benchmarking discipline — **BEHIND**

**What we do (code):** Real per-witness checks (`verification/witnesses.py`: SuiteWitness,
SmokeWitness, NumericalWitness, NumericalContinuityWitness), numerical baselines with PROBE mode,
regression-memory checks, judge golden tests (`tests/unit/`), and a self-recall eval
(`ecosystem_eval.py`). This is more eval rigor than most personal stacks.

**Frontier:** **Inspect AI** (UK AISI) [GOV/OSS] — MIT-licensed, multi-provider, 200+ evals in
`inspect_evals`, agentic tasks, sandboxed scoring, an approval system, and the
**"production failure → eval case → CI gate"** loop now standard at Braintrust/DeepEval. The wider
push is "from models to agents" standardized evaluation. [GOV/OSS/PREPRINT]
([Inspect AI](https://github.com/UKGovernmentBEIS/inspect_evals),
[Inspect sandboxing toolkit](https://www.aisi.gov.uk/blog/the-inspect-sandboxing-toolkit-scalable-and-secure-ai-agent-evaluations),
[standardized eval](https://arxiv.org/pdf/2602.18029))

**The benchmark that targets our exact threat — SpecBench.** Two 2026 papers share the name:
- *SpecBench: Measuring Reward Hacking in Long-Horizon Coding Agents* [PREPRINT] — 30 systems-level
  coding tasks that **separate VISIBLE validation tests from HELD-OUT tests** and report the
  **validation-minus-held-out gap**, which grows **~28pp per 10× increase in code size**. This is the
  canonical external measure of *the verifier being gamed* — precisely the failure our judge
  degenerate-output guard and Sentinel's fabricated-artifact / validation-minus-held-out rules exist
  to catch. ([arXiv 2605.21384](https://arxiv.org/abs/2605.21384))
- *SpecBench: Evaluating Specification-Level Reasoning for SWE Agents* [PREPRINT] — RFC-derived
  spec-reasoning tasks; **best agent (GPT-5.4) scores 44.4%**, showing how far spec-faithful coding
  still has to go. ([arXiv 2605.30314](https://arxiv.org/abs/2605.30314))

**Honest gap:** Our witnesses are **bespoke glue**, not a standardized harness; we keep numerical
baselines but **no held-out benchmark suite**, **no adversarial master-key eval for the judge**, and
**no LongMemEval-style memory probe**. Sharpest of all: the *validation-vs-held-out witness* concept
we already designed (Overmind's held-out-baseline policy + Sentinel's validation-minus-held-out rule)
is **exactly what SpecBench formalizes and quantifies** — yet **we have run it zero times and have no
number**. We cannot put a figure on our judge's robustness or our reward-hacking resistance. The
frontier's defining trait in 2026 is *measured* evaluation; ours is *constructed* assurance. This is
our clearest, cheapest-to-close gap — and SpecBench is the off-the-shelf instrument to close it.

### 5. Truth-recovery / groundedness — **AHEAD (operational); PARITY on formal groundedness**

**What we do (code):** Fail-closed everywhere — missing baseline ⇒ **UNVERIFIED**, never CERTIFIED
(`cert_bundle.Arbitrator`); the SKIP-as-pass lesson is encoded as a distinct verdict. The judge
degenerate guard (Dim 2) is a truth-recovery defense. `source_hash` freshness invalidates stale
memory. Sentinel ships a **fabrication rule family** — `P1-fabrication-implausible-precision`,
`-orphan-trial`, `-round-number-cluster`, `-self-contradiction`, `-temporal-impossibility`,
`P0-citation-cascade`, `P1-hallucinated-python-import`, `P1-claim-grounding` (per the BadScientist /
hallucinated-import papers).

**Frontier:** *Grounded Continuation* [PREPRINT] — a linear-time runtime verifier that builds an
explicit **claim→evidence dependency graph** and **propagates retractions** to invalidate dependent
conclusions. Plus production groundedness scorers Vectara **HHEM-2.1** and Cleanlab **TLM**.
([arXiv 2605.14175](https://arxiv.org/abs/2605.14175),
[HHEM leaderboard](https://github.com/vectara/hallucination-leaderboard))

**The reward-hacking framing — SpecBench.** Our whole threat model is "a project fabricates results
to game the verifier." *SpecBench: Measuring Reward Hacking in Long-Horizon Coding Agents* [PREPRINT]
operationalizes exactly this as the **validation-minus-held-out gap** (grows ~28pp per 10× code
size). Overmind's held-out-baseline policy (missing baseline ⇒ UNVERIFIED) and Sentinel's
validation-minus-held-out / fabricated-artifact rules are the *defense* for the failure SpecBench
*measures*. We have the right concept; we have **no measured SpecBench score** to prove the defense
works. ([arXiv 2605.21384](https://arxiv.org/abs/2605.21384))

**Honest call:** On *operational* truth-recovery — abstention as a first-class verdict, fail-closed
gates, signed verdicts, fabrication linting — we are **ahead of typical deployments** and this is the
deliberate core of the whole stack. Two gaps keep it honest: (1) *empirical* — we have never run
SpecBench (or any reward-hacking benchmark) against our gates, so the defense is asserted not proven;
(2) *formal* — our groundedness is **rule/witness-based**, not a **claim→evidence graph with
retraction propagation** (when a source changes we recompute a hash; we don't yet invalidate the
transitive closure of downstream conclusions — the deferred B2 item). So: ahead in practice,
unproven on the benchmark, at parity-to-slightly-behind on the formal mechanism.

### 6. Multi-engine cross-checking — **AHEAD**

**What we do (code):** Real cross-*family* quorum (`judge_factory.py`): `ENGINE_FAMILY` map
(claude→anthropic, codex→openai, agy/gemini→google, local, stub), `estimate_effective_votes()` using
`distinct_families + 0.25·(nominal − distinct_families)`, a `quorum_correlated_panel` concern, and
the effective-vote count surfaced in the signed bundle. Backends actually exist for Claude / Codex /
Gemini(agy) / local / stub with a `FallbackBackend` chain.

**Frontier:** *Nine Judges, Two Effective Votes* [PREPRINT] — a 9-judge panel gave ~2.2 effective
independent votes; correlated errors mean a same-family panel overstates its independence. The
*Replacing Judges with Juries (PoLL)* line argues diverse small models beat one big judge, and
*preference-leakage* work (ICLR 2026) shows same-family generator/evaluator pairs are contaminated.
([arXiv 2605.29800](https://arxiv.org/abs/2605.29800),
[PoLL](https://arxiv.org/abs/2404.18796))

**Honest call:** This is a genuine, rare strength. Most production "LLM-judge" setups use a single
model or a same-family panel; we cross-check across **three different model families** and, crucially,
**measure and surface the decorrelation** (effective votes), implementing the exact 2026 finding most
panels ignore. **Honest caveats:** quorum is opt-in (default is single-engine fallback);
decorrelation is **warn-only, not hard-enforced** (a `claude,codex,codex-noreen` panel still runs,
just flagged); and we should never market "3 engines" as "3 independent checks" — our own estimator
says it's ~2.25.

### 7. Sandboxing / safety — **MIXED (AHEAD on policy invariants, BEHIND on execution isolation)**

**What we do (code):** `infra_invariants.py` enforces deterministic invariants: **force-push
disabled**, Codex OAuth freshness, finding-log health, doc freshness, judge-engine-config validity —
fail-soft on missing optional inputs, never prints secrets. CertBundles are signed (Ed25519 / HMAC /
Sigstore) with replay protection. Sentinel's bypass log is a **tamper-evident SHA256 hash chain**.
But witness code (test suites, smoke imports, numerical runs) executes as **host subprocesses**.

**Frontier:** The **Inspect Sandboxing Toolkit** and the E2B / Modal / Daytona / Fly microVM
ecosystem give per-trial wiped+reseeded isolation with 5–30ms snapshot-restore; *Deterministic
Pre-Action Authorization* formalizes gating tool calls before execution. [GOV/OSS/PREPRINT]
([Inspect sandboxing](https://www.aisi.gov.uk/blog/the-inspect-sandboxing-toolkit-scalable-and-secure-ai-agent-evaluations),
[pre-action authorization](https://arxiv.org/pdf/2603.20953))

**Honest call:** Our **policy/governance invariants are unusually strong** (force-push-off as a
checked invariant, hash-chained bypass audit, signed verdicts — most stacks have none of this). But
our **execution isolation is weak**: we run untrusted-ish project code as subprocesses on the host,
not in a microVM/gVisor sandbox. For a personal portfolio of self-authored repos the blast radius is
low, so this is acceptable today — but it is squarely behind the frontier's isolation model and would
be a real risk the moment we verify third-party or agent-generated code at scale.

### 8. Observability — **PARITY (BEHIND on tracing)**

**What we do (code):** `telemetry/session_metrics.py`, `token_metrics.py`, JSONL finding streams
(`STUCK_FAILURES.jsonl` / `sentinel-findings.jsonl`), signed bundles as audit artifacts, nightly
reports, Morning Watchdog thresholds, bypass-log verification. For a single-node system this is
respectable.

**Frontier:** LangSmith / Langfuse / OpenTelemetry-for-agents give span-level trace observability of
every model call, tool call, and handoff, which is now table stakes in production agent stacks.
([harness engineering list](https://github.com/ai-boost/awesome-harness-engineering))

**Honest call:** We have good *aggregate* metrics and excellent *audit* artifacts, but **no
distributed/span tracing** — you can't yet open a single trace and watch a verdict's full
witness→judge→arbitrator path with token/latency spans. Parity on metrics+audit, behind on tracing.

### 9. Scalability (the cluster) — **BEHIND**

**What we do (code):** Single `Orchestrator`, sequential nightly verify over the portfolio on one
machine. Beast is single-process with an interval loop. There is **no remote-runner, no task
dispatch, no node registry** in code.

**Frontier:** Distributed sandboxed agent fleets, parallel eval at scale, orchestrator-worker fan-out
(Anthropic's multi-agent research system documents the pattern *and* its ~15× token cost).

**Honest call:** **BEHIND, and the gap is wider than the roadmap implies** — the "multi-node Tailscale
cluster" is, per §0, **undocumented and not in code**. Today we are firmly single-node. A cluster
*would* directly attack our biggest scaling bottleneck (sequential nightly over a growing portfolio),
but scoring must reflect shipped reality: this is a plan, not a capability.

### 10. Reproducibility — **AHEAD**

**What we do (code):** Signed CertBundle (Ed25519 default; HMAC/Sigstore fallback) with
`verify_signature` + `verify_freshness` both required (replay protection); **immutable scope_lock**;
version-controlled numerical baselines with continuity checks; deterministic stdlib-only file_index;
seeded PRNGs per the house rules.

**Frontier:** Reproducible Builds + **Kettle** (verifiable build provenance in a confidential VM) and
**C2PA v2.3** text-provenance manifests (relevant to EU AI Act Art. 50 from 2026-08-02). These mostly
**validate** our signing approach. ([Reproducible Builds](https://reproducible-builds.org/reports/2026-05/))

**Honest call:** Genuinely ahead of typical practice — signed, replay-protected, immutably-scoped
verdicts with numerical baselines is strong reproducibility hygiene. Behind only on full
**toolchain/build provenance** (record source commit + toolchain + artifact digests, TEE-backed) and
standards-based provenance manifests, both of which are optional add-ons rather than gaps in
correctness.

---

## 3. Top 3 genuine strengths (real, not aspirational)

1. **Truth-first verification as the architecture, not a feature.** Fail-closed gates, a distinct
   **UNVERIFIED** verdict, the degenerate-output guard, and Sentinel's fabrication-rule family mean
   the default failure mode is *abstain*, not *false-pass*. This is the exact discipline the 2026
   LLM-judge security literature is converging on, and we encode it in shipped code with signed
   evidence. (Dims 5, 2, 10)

2. **Cross-family multi-engine quorum with measured decorrelation.** We don't just run multiple
   judges — we map them to model families and surface an *effective-vote* estimate, implementing the
   "Nine Judges, Two Effective Votes" finding that most production panels ignore. Genuinely rare.
   (Dim 6)

3. **A working temporal-validity + consolidation memory system.** Two layers (markdown + SQLite/FTS5)
   with validity windows, per-type decay, source-hash freshness, and scheduled consolidation — the
   Graphiti/A-MEM/sleep-time-compute ideas, actually built and running on a nightly schedule. (Dim 3)

## 4. Top 3 genuine gaps (honest, specific)

1. **Nothing is measured.** Our judge robustness, memory recall, and verifier accuracy are
   asserted-by-construction and **never benchmarked** — no adversarial master-key eval, no
   LongMemEval probe, no held-out witness suite, no standardized harness (Inspect AI). In a field
   whose defining 2026 trait is *measured* evaluation, this is the single weakest spot. (Dim 4)

2. **Single-node reality vs. cluster aspiration.** Overmind is a sequential, one-machine nightly
   verifier; the "multi-node Tailscale cluster" has **no code or docs**. Scalability is our furthest-
   behind dimension and the roadmap currently overstates it. (Dim 9)

3. **Heuristic guards where the frontier uses learned/graph mechanisms.** Our judge is a
   prompt+regex guard, not a trained robust reward model (CompassVerifier/Master-RM); our
   groundedness is rule-based, not a claim→evidence graph with retraction propagation
   (Grounded Continuation); our code execution is host-subprocess, not microVM-sandboxed. Each is
   "right idea, lighter mechanism." (Dims 2, 5, 7)

## 5. Prioritized path to / past the frontier

Ordered by **(value ÷ effort), truth-first**:

1. **★ Make quality measurable (highest leverage, low effort).** Stand up three small held-out evals:
   (a) **★ a SpecBench-style validation-vs-held-out eval for our judge + witnesses** — run
   [SpecBench](https://arxiv.org/abs/2605.21384) (or a SpecBench-shaped harness over our own repos)
   that hides held-out tests from the verifier, then **publish our validation-minus-held-out gap** as
   the concrete number proving (or disproving) that the degenerate-output guard + held-out-baseline
   policy + Sentinel fabricated-artifact rules actually resist reward hacking. This *is* the
   adversarial held-out eval, and SpecBench is the off-the-shelf instrument — truth-first means we
   publish the number rather than assert the defense. (b) a **LongMemEval-style probe** for the memory
   store → publish recall; (c) wrap our witnesses behind the **Inspect AI** harness or at least adopt
   its *production-failure → eval-case → CI-gate* loop. This converts three "parity/behind-by-assertion"
   dimensions into "ahead-by-evidence" and is the precondition for honestly claiming any robustness.
   (Closes Dim 4; substantiates Dims 2, 5; LongMemEval substantiates Dim 3.)

2. **Flip the cheap, already-built switches.** Run the judge golden-set once and **default
   `OVERMIND_JUDGE_COT` ON** (built, off by default); add **cost-aware engine routing** (cheap/local
   first, escalate on low confidence — deferred C2) to cut quorum's ~15× token cost. (Dims 1, 2)

3. **Decide the cluster: build it or stop citing it.** Either implement a real remote-runner over
   Tailscale (node registry + parallel witness dispatch + the delta-skip hash-gate so only
   changed/at-risk projects run) — which directly fixes the sequential-nightly bottleneck — **or**
   remove "multi-node cluster" from any status doc until it exists. Truth-first demands one or the
   other. (Dim 9)

4. **Upgrade two mechanisms toward the frontier (medium effort, plan):** (a) a **claim→evidence
   dependency graph with retraction propagation** to replace flat source-hash freshness (B2,
   formalizes "missing premise ⇒ invalidate dependents"); (b) **microVM/gVisor execution sandboxing**
   for witnesses *if/when* we ever verify third-party or agent-generated code. (Dims 5, 7)

5. **Cross-repo contract-impact verification (B1).** The one capability the whole industry
   standardized on in 2026 that we lack: when a shared module/schema changes, fan out to dependent
   projects' witnesses. High value, high effort — sequence before any delta-skip optimization so we
   never skip a project whose upstream dependency changed. (Dims 1, 9)

---

## 6. Source maturity notes

- **Strongest / primary:** Inspect AI (gov-backed OSS), Anthropic/Microsoft engineering pages,
  Reproducible Builds report, Vectara HHEM, the *One Token to Fool* paper (now at OpenReview).
- **Directional preprints (single-lab, adopt the idea, validate the number ourselves):** Nine-Judges
  decorrelation, Grounded-Continuation, the reward-hacking cluster, bias-mitigation, CompassVerifier,
  and **SpecBench** ([2605.21384](https://arxiv.org/abs/2605.21384) reward-hacking /
  [2605.30314](https://arxiv.org/abs/2605.30314) spec-reasoning) — the SpecBench numbers (~28pp/10×
  gap; GPT-5.4 44.4%) are *their* measurements, not ours; the action item is to **run it and publish
  our own gap**, not to quote theirs as if it were our score.
- **Orientation only (not cited as fact):** vendor "best-of-2026" memory listicles and LongMemEval
  win-rates — quoted as *directional* magnitudes, not verified benchmarks; verify before quoting.

*This benchmark scores shipped code as of 2026-06-24. Re-run after the §5 evals exist — several
"parity/behind-by-assertion" calls should become "ahead-by-evidence" once measured.*
