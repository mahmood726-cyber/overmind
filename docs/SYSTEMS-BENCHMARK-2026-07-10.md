# Systems Benchmark 2026-07-10 — The Harness vs. the 2026 Frontier

**Date:** 2026-07-10
**Author:** evidence-grounded benchmark (Claude Code / Opus 4.8) for Mahmood
**Method:** read the *actual current code* of Sentinel, Overmind/TruthCert, Dispatch (`cluster-harness`
+ `overmind/cluster`), the two memory layers, and the SSH cluster transport — via three independent
read-only inventory agents that reported `file:line` evidence — then scanned the latest (mid-2026)
public agentic-engineering research (web + arXiv). Builds on, and supersedes where code has changed,
[`SYSTEMS-BENCHMARK-VS-FRONTIER.md`](SYSTEMS-BENCHMARK-VS-FRONTIER.md) (2026-06-24) and its
[adoption](AI-FRONTIER-ADOPTION.md) / [closing-progress](FRONTIER-CLOSING-PROGRESS.md) logs.

> **Truth-first contract.** No flattery. "Ahead / at-par / behind" is scored against **what the code
> does today**, not what it aspires to. Where an advantage is real it's marked real; where it is
> asserted-by-construction, it says so; where a capability is a stub, it's flagged **STUB**. Frontier
> sources are cited as `[PEER]` (accepted venue), `[PREPRINT]` (arXiv, not peer-reviewed), or
> `[PROD/OSS]`. Preprint numbers are *their* measurements, directional — not our scores.

---

## 0. Three honesty flags (read first)

1. **Cross-vendor verification is PAUSED as of this writing** — and a live probe (§1.5-LIVE) confirms why.
   Codex (both seats) and agy are out of quota / degraded; headless Claude has no non-interactive path on
   the nodes. So the differentiator — a live ≥2-distinct-family consensus — **cannot run today.** Every
   cross-vendor *completion* number is from *prior* runs (2026-07-06/07, `harness.db`), **not re-verified
   today.** New this run: I **did** live-verify the substrate *underneath* the vendor call (SSH transport,
   routing, fan-out, consensus-or-flag, anti-wedge timeouts — all measured working), and I found the "all
   three nodes online" update is **only half true: pc2 is offline** (Tailscale "last seen 4d ago"; SSH
   times out). 2 of 3 nodes (pc1 + laptop) are up. The moat exists in code and its plumbing is now
   live-proven; its fuel (vendor availability) and one node (pc2) are intermittent.

2. **Every eval number here is fixture-based, not live-model.** `python -m evals.run_all` (13 evals)
   ran clean and reproduces every claimed delta — but on **deterministic seeded/stub panels**, not real
   claude/codex/agy calls. The evals prove the *harness logic* (before→after deltas, floor holds,
   guard holds); they do **not** prove real-vendor judge accuracy. Two evals are also saturated at the
   ceiling on small keyword-distinct fixtures (memory recall 100%, degenerate false-pass 0%).

3. **The June benchmark is materially out of date — mostly because the gaps got closed.** Between
   2026-06-24 and today the `frontier-closing` work landed on master and the cluster became real. Two
   June verdicts are now wrong in our favor and one prior count was wrong:
   - "Multi-node Tailscale cluster does not exist in code" → **FALSE now.** Real SSH transport exists
     and has executed 15 cross-machine, cross-vendor jobs (`cluster-harness/harness.db`).
   - "Nothing is measured" → **largely closed.** 13 harness evals + a private reconstruction
     ground-truth corpus now exist.
   - Sentinel "≈53 rules / 21 blocking" → **corrected to 64 rules / 24 blocking** (verified via
     `python -m sentinel list-rules`).

---

## 1. Component-by-component scorecard

Five pieces, each scored against its **nearest published frontier system/paper**.

| Component | What it is (verified) | Nearest frontier | Verdict | The specific gap |
|---|---|---|---|---|
| **Sentinel** | 64-rule / 24-blocking pre-push git-hook; fabrication-truth family; diff-scoped; hash-chained bypass | VibeGuard, AI-SAST (semantic), semgrep, SLSA/sigstore | **AT-PAR breadth, AHEAD on truth-grounding, BEHIND on mechanism** | 42/64 rules are regex (evadable); zero SLSA/attestation; unsigned manifest (drifting now); P/R never measured |
| **Overmind + TruthCert** | multi-witness → 5-state arbitrator (incl UNVERIFIED); 3-layer objective floor; signed CertBundle; 13 measured evals | CompassVerifier `[PEER]`, Inspect AI, conformal-abstention, SpecBench | **AHEAD on discipline, now AT-PAR on measurement, BEHIND on learned verifier + live measurement** | judge is a regex/prompt guard not a trained RM; evals are fixtures; objective-gate is WARN-only in the general path |
| **Dispatch** | lease-based coordinator, 2-stage capability routing (lane×node), anti-wedge runner, consensus-or-flag; = the single control plane | LangGraph durable graph, supervisor topology, Magentic-One ledger, RouteLLM | **AT-PAR (adequate for domain), AHEAD on anti-wedge + vendor-distinct routing** | no durable/resumable graph or checkpoint-resume; routing is capability-based, not a learned cost-optimal router |
| **Memory** | (a) 11-file markdown (wikilinks, **no temporal fields**); (b) SQLite/FTS5 3,201 rows: decay + temporal supersede + source-hash + claim-graph + MiniLM + dream-consolidation, wired | Graphiti/Zep (temporal KG), A-MEM, Mem0/Letta, OCR-Memory | **AT-PAR on architecture, AHEAD on shipped claim-graph retraction, BEHIND on entity graph + measured recall** | no typed entity graph; the two layers are unbridged (markdown has no temporal metadata); never run on LongMemEval |
| **Multi-PC / cluster** | REAL Tailscale-SSH transport; 15 executed cross-machine cross-vendor jobs; delta-skip + contract-impact gate; A/B/C benchmark | Distributed sandboxed fleets; orchestrator-worker; co-failure-ceiling theory | **AHEAD on cross-vendor consensus-or-flag with *measured* heterogeneity benefit; BEHIND on scale + isolation** | vendor reliability is the binding constraint (paused today); node registry hand-seeded; remote isolation is a STUB |

### 1.1 Sentinel — the pre-push truth-and-safety gate

**Verified today:** `python -m sentinel list-rules` → **64 rules** (57 Python plugins + 7 YAML),
**24 BLOCK / 36 WARN / 4 INFO** (count from the `[BLOCK]` label, *not* the `P0/P1/P2` prefix — 6 `P1-`
rules block, one `P0-` only warns). Taxonomy: security/secrets (`P1-leaked-secret`, `P0-placeholder-hmac`,
`P0-hmac-compare-eq`, `P0-unsafe-eval-exec`), code-safety (`P1-py/js-parse-check`, `P1-empty-dataframe-access`,
`P1-regex-catastrophic-backtrack`, `P1-silent-failure-sentinel`), **fabrication/truth-grounding**
(`P1-fabrication-*`, `P1-claim-grounding`, `P1-hallucinated-python-import` — cites *BadScientist*,
arXiv:2510.18003), supply-chain (`P1-js-lockfile-present`, `P0-citation-cascade`, `P0-baseline-drift`),
housekeeping/registry (`P0-hardcoded-local-path`, `P0-registry-drift`). Mechanism: **42/64 are pure regex**;
only `hallucinated_python_import` uses `import ast`; `py_parse_check` uses `compile()`; the semantic
`hallucination_classifier` is a *scaffold* (local "no-naked-numbers" heuristic by default; the Lynx-8B/HHEM
path is unwired). Bypass = `SENTINEL_BYPASS=1` → SHA-256 **hash-chained** log (tamper-evident, no secret key).

**Frontier comparator — VibeGuard: A Security Gate Framework for AI-Generated Code** `[PREPRINT]`
(arXiv:2604.01052): a pre-publish gate over five categories (artifact hygiene, packaging-config drift,
source-map exposure, hardcoded secrets, supply-chain), reporting **100% recall / 89.5% precision (F1 94.4%)**
on 8 synthetic projects. The 2026 AI-SAST direction is **semantic/dataflow** analysis over pattern-matching
([Augment Code AI-SAST guide](https://www.augmentcode.com/guides/what-is-ai-sast)); *Broken by Default*
`[PREPRINT]` (arXiv:2604.05292) formally verifies that ~45% of AI-generated code ships an exploitable vuln.
Supply-chain frontier = **SLSA provenance + signed attestation** ([Cloudsmith 2026 guide](https://cloudsmith.com/blog/the-2026-guide-to-software-supply-chain-security-from-static-sboms-to-agentic-governance)).

**Honest call:** Sentinel is **broader than VibeGuard** (VibeGuard's 5 categories are a subset of Sentinel's
families) and its **fabrication/truth-grounding family is a genuine rarity** — general code guardrails don't
lint for implausible-precision or round-number-cluster fabrication. But it is **behind on mechanism** (regex,
not AST/dataflow — `e="ev"+"al"; getattr(builtins,e)(...)` evades `unsafe_eval_exec`), has **zero
supply-chain attestation** (no SLSA/sigstore/in-toto anywhere), and **has never published a precision/recall
number** the way VibeGuard did. Live hygiene finding: `sentinel verify-rules` reports **DRIFT right now**
(`P0-hardcoded-local-path.yaml` modified without regenerating the manifest) — the integrity guarantee is only
as strong as the discipline of re-running `--update`.

### 1.2 Overmind + TruthCert — the verifier

**Verified today (all present on master):** witnesses `SuiteWitness` / `SmokeWitness` / `NumericalWitness` /
`NumericalContinuityWitness` (`witnesses.py`, `numerical_continuity.py`); `Arbitrator` 5-state verdict incl.
**UNVERIFIED** for PASS-on-missing-baseline (`cert_bundle.py:102`); **signed CertBundle** (Ed25519 default,
HMAC/Sigstore fallback) with `verify_signature` + `verify_freshness` replay protection and immutable
`scope_lock`. Judge (`llm_judge.py`): degenerate-output guard (`:458`), **CoT+rubric DEFAULT-ON**
(`OVERMIND_JUDGE_COT` defaults `"1"`, `:259`), input-side injection guard (`injection_tamper_reason` +
`PromptInjectionScanner`, `:505`). Factory (`judge_factory.py`): `ENGINE_FAMILY` map, `estimate_effective_votes()`,
**different-family quorum ENFORCED by default** (`OVERMIND_JUDGE_QUORUM_ENFORCE` defaults `"1"`, `:263`),
`RoutedJudge` cost-aware escalation. Plus `claim_graph.py` (retraction propagation), `verdict_trace.py`
(OTel-shaped spans; Arbitrator instrumented), `contract_impact.py` (transitive closure).

The **objective-witness floor is three layers**, an important nuance: (1) a **hard block** in the typed
verdict path — `claude_json_verdict.py:159` downgrades a judge PASS to abstain if `objective_witness` is
missing/failed; (2) the **Arbitrator UNVERIFIED** state; (3) a **shadow audit** (`objective_gate.py`,
`OVERMIND_OBJECTIVE_GATE_AUDIT='shadow'`) that only **WARNs** — so in the *general* orchestrator path the
floor is advisory, and the hard block applies only on the typed `claude -p --json-schema` path.

**Frontier comparators:** *CompassVerifier* `[PEER, EMNLP 2025]` (arXiv:2508.03686) — a **trained** robust
verifier/reward model; *Security in LLM-as-a-Judge: A Comprehensive SoK* `[PREPRINT]` (arXiv:2603.29403) and
*One Token to Fool LLM-as-a-Judge* `[PREPRINT]` (arXiv:2507.08794) — master-key attacks; *Beyond Semantic
Manipulation: Token-Space Attacks on Reward Models* `[PREPRINT]` (arXiv:2604.02686) — a **newer** attack class
beyond master-keys; *SpecBench (reward-hacking)* `[PREPRINT]` (arXiv:2605.21384); *Inspect AI* `[GOV/OSS]`.

**Honest call:** On **operational discipline** — fail-closed, first-class UNVERIFIED, degenerate guard,
enforced-family quorum, signed replay-protected verdicts — Overmind is **ahead of typical LLM-judge
deployments** and this is now the June→July win: it is **no longer "unmeasured."** 13 evals give real deltas
(`specbench_gap` 33.3%, `reward_hack_heldout_catch` 100%/5-of-5, `degenerate_false_pass` 0%,
`injection_boundary` 50%→0%). **But** the judge is still a **regex/prompt guard, not a trained verifier**
(CompassVerifier-class), the evals are **fixtures not live**, and there is one measured, admitted leak:
`injection_clean_boundary_false_pass = 1.0` — a bare planted `VERDICT: PASS` with no attack phrase is
indistinguishable from a genuine verdict by output scanning (closable only via the trusted tool-call channel,
which the `claude_json_verdict` path partially provides).

### 1.3 Dispatch — the control plane / router

**Verified today:** two real implementations. `C:\Projects\cluster-harness` is the battle-tested one — a
SQLite-WAL lease-based `coordinator.py` with two-stage routing (`router.py:68`: lane-by-jobtype then
node-by-capacity/locality), an **anti-wedge `runner.py`** (NUL stdin, hard wall-clock timeout, `taskkill /T /F`
tree-kill, background pipe-drain — the single chokepoint every command passes through), `consensus.py`
vendor-distinct truth-gate, and INFRA-reroute/requeue relaunch. `overmind/cluster/scheduler.py` is a cleaner
re-implementation (capability-aware, load-balancing, requeue-safe). Per `WORLD_CLASS_SPEC.md §0.5`, **Dispatch
is the single control plane** — the conductor that routes each unit of work to the right vendor on the right
node, gates, and moves on; it does not do the heavy reasoning.

**Frontier comparators:** the 2026 production default is the **supervisor topology** (LangGraph Supervisor,
OpenAI Agents SDK handoffs, Claude subagents all converge on it —
[5 patterns](https://www.digitalapplied.com/blog/multi-agent-orchestration-5-patterns-that-work)); **LangGraph**
adds durable cyclic graphs with **checkpoint-at-every-step** persistence and time-travel; **Magentic-One**
uses a task/progress ledger; cost-aware routing (RouteLLM, *AdaptOrch* arXiv:2602.16873) cascades cheap→expensive.
2026 production overhead figures: ~+58% tokens for independent multi-agent, ~+285% for centralized supervisor.

**Honest call:** For a **deterministic verification router** this is **at-par and adequate** — a full agent-graph
framework would be over-engineering. Dispatch is **ahead on two domain-specific things**: the anti-wedge process
robustness (tree-kill + NUL-stdin + timeout as the universal chokepoint — most frameworks don't have this
hardening) and **vendor-distinct panel assembly** as a first-class routing primitive. **Behind on:** no durable,
resumable **graph** with checkpoint-resume (a wedged multi-day job restarts a lane, it doesn't resume a graph
node), and routing is **capability-based, not a learned cost-optimal router** (no RouteLLM-style escalation
signal driving vendor choice).

### 1.4 Memory — cross-session knowledge

**Verified today:** two real but **unbridged** layers. (a) The markdown auto-memory (11 fact files +
`MEMORY.md`, `[[wikilink]]` graph) — human-curated prose that, corrected against the brief, **has NO temporal
frontmatter** (`is_current`/`superseded_by`/`valid_from` are absent; that lives only in layer b). (b) The
Overmind SQLite/FTS5 `MemoryStore` — **3,201 live rows**, per-type decay (`DEFAULT_DECAY_RATES`), temporal
`supersede()`/`expire_old()`, `source_hash` freshness + **claim-graph transitive invalidation**
(`invalidate_stale_with_propagation()`, `propagate_retraction()`), MiniLM-L6-v2 embeddings with FTS5 fallback,
and `dream_engine.dream()` consolidation (expire→extract→cluster→merge→prune) — **wired** into the orchestrator,
nightly runner, and session-stop hooks.

**Frontier comparators:** Zep/**Graphiti** (temporal knowledge graph, **63.8% LongMemEval** vs Mem0 49.0%);
**A-MEM** (Zettelkasten, arXiv:2502.12110); **sleep-time compute** (arXiv:2504.13171); the **optical-memory**
line the brief flagged — **OCR-Memory** `[PREPRINT]` (arXiv:2604.26622) stores histories as compressed
multi-resolution images (>10× token compression, 98.5% retrieval @4k, 100% verbatim fidelity via deterministic
fetch), built on **DeepSeek-OCR** (arXiv:2510.18234); the **Memory in the Age of AI Agents** survey
(arXiv:2512.13564).

**Honest call:** The **architecture is frontier-aligned and shipped** — temporal validity, decay, source-hash
freshness, dream-consolidation, and (rare) a **claim→evidence retraction graph** that is not just designed but
**eval-proven** (transitive recall 33%→100%). Two real gaps: (1) **no typed entity-relationship graph** —
Graphiti reasons over a temporal *entity* graph; we have wikilinks + FTS5 + a claim/dependency graph, which is
shallower on *relational* reasoning; (2) **never benchmarked** — memory recall is 100% on a saturated
keyword-distinct fixture, never on LongMemEval. **OCR-Memory is complementary, not a threat** (it solves
long-trajectory context compression; our store solves durable fact validity) — worth noting as a *future*
lane if trajectory logs ever blow the context window, not a gap today.

### 1.5 Multi-PC / cluster — heterogeneous-vendor fan-out

**Verified today — the biggest June→July change.** `cluster-harness/harness/nodes.py:31` hardcodes real
Tailscale nodes (`laptop = mahmo@100.80.183.43`, `pc2 = user@100.127.107.46`, key `node2_ed25519`);
`overmind/cluster/transport.py:230` is explicit: `RemoteExecutor = SSHExecutor` with the comment *"The old name
implied 'deferred/stub'; it is now the real SSH executor"* — the `NotImplementedError` is gone. **Decisive
proof of real runs:** `cluster-harness/harness.db` holds **15 executed job rows** across three machines and
multiple vendors — e.g. `job 12 → pc2/codexA over SSH → "VERDICT Q=4.7761 tau2=0.0155 pooled=0.34…"` (a real
meta-analysis output), `job 8 → laptop/codexA rc=255` (a real SSH infra failure, correctly recorded). The
`SshClaudeBackend` (`judge_backends.py:125`) ran the A/B/C benchmark via laptop-subscription over SSH.

**Frontier comparators:** distributed sandboxed agent fleets and orchestrator-worker fan-out (Anthropic's
multi-agent research system documents the pattern *and* its ~15× token cost); and the theory that **bounds**
this whole design — ***When Does Combining Language Models Help? A Co-Failure Ceiling…Across 67 Frontier
Models*** `[PREPRINT]` (arXiv:2606.27288): ensemble accuracy cannot exceed **1 − β**, where β is the rate at
which **all** models fail on the *same* query; β (all-wrong rate) matters more than pairwise correlation ρ; and
"**on checkable tasks, combining models rarely beats the single best model without a strong query-level routing
signal** — gains come from models failing on *different* questions." Related: *Mixture of Complementary Agents*
(arXiv:2605.24048), *Mixture-of-Models* (arXiv:2601.16863), *Nine Judges, Two Effective Votes* (arXiv:2605.29800).

**Honest call — this is where we are genuinely ahead of the *published* frontier, and it's measured.** The
A/B/C benchmark (held-out FULL 139 + frozen 73, two-slice confirmed) shows the heterogeneous **Arm C
(Claude+agy+objective floor) catches 0.921 defects vs single-agent A 0.802 and homogeneous-triple B 0.770** —
and critically **B < A** (a same-vendor majority-of-3 catches *fewer* defects than one agent, because it
suppresses nondeterministic single-model catches). That is our own corpus **independently reproducing the
co-failure-ceiling finding**: the win comes from *heterogeneity* (a different vendor), not vote count; and the
gap-analysis confirms the ceiling (only 1 correlated blind-spot in 126 → a 3rd vendor buys ≈1 marginal defect,
diminishing returns). Most production "multi-judge" stacks never prove heterogeneity beats homogeneity; we did.
**Behind on:** portfolio scale, hand-seeded node registry, **remote execution isolation is a STUB**
(`isolation.py:98`: `run_in_container()` always returns SKIP; falls back to worktree), and — the binding
constraint — **vendor reliability** (the A/B/C verdict was `NOT_PROVEN` on the false-alarm clause until the
conformal gate landed, and cross-vendor is *paused today* on quota).

#### 1.5-LIVE — measured 3-node benchmark (2026-07-10, this run)

Prompted by "all three nodes online," I ran a live probe. **The claim only half-holds: 2 of 3 nodes are
reachable.** This is the honest live picture — read-only, no node-repo writes, vendor calls not issued.

**A. Reachability + health (live)**

| Node | Role (cap) | Tailscale | SSH round-trip (read-only `hostname`) | Status |
|---|---|---|---|---|
| **pc1** | local controller (2) | self | n/a (local) | **UP** |
| **laptop** `100.80.183.43` | ssh (3) | `pong` **2 ms** direct (56 ms first pkt via DERP-lhr, then IPv6 direct) | rc=0, host=`mahmood`, **mean ≈692 ms** over 5 reps (619–791 ms, *full* handshake+auth+cmd each call) | **UP** |
| **pc2** `100.127.107.46` | ssh (3) | **offline, "last seen 4d ago"**, ping → *no reply* | rc=255 `Connection timed out`, **bounded at 10.18 s** by `ConnectTimeout=10` | **DOWN** |

Two real security/perf notes surfaced live: the laptop SSH server emits a **post-quantum-KEX warning**
(not using a PQ key exchange — "store-now-decrypt-later" exposure; server needs an OpenSSH upgrade), and the
laptop's steady-state path is 2 ms but a *cold* SSH round-trip is ~0.7 s (handshake-dominated — batch remote
work, don't chatter).

**B. Plumbing exercised end-to-end, up to (not incl.) the vendor call — all measured**

| Layer | What ran | Measured |
|---|---|---|
| **Fan-out setup** | `nodes.build_command` over all 3 nodes × 4 lanes | **12 commands in <0.1 ms** total (sub-µs each); local argv for pc1 (argc 5, no ssh) vs SSH-wrapped for laptop/pc2 (argc 12) — plumbing correct |
| **Node-selection** | real `router.route()`, real `capabilities.json`, DB opened **read-only** | **0.0–0.8 ms/decision**; correct locality (workspace job → pinned to pc1; offload → pc2/laptop) |
| **Consensus-or-flag** | real `consensus.evaluate()`, synthetic lane answers | **<0.1 ms/adjudication**; ACCEPT iff ≥2 *distinct* vendors agree (numeric to **1e-9**, or matching text verdict); FLAG w/ quantified spread on disagreement; **`cannot_form_quorum`** when only 1 vendor participates ("*two clones of one vendor do not count*") |
| **Vendor call** | — | **QUOTA-BLOCKED — not issued.** No codex/agy completion faked. |
| **Wedge/timeout (local)** | `runner.run(sleep 30, timeout=3.0)` | killed at **3201 ms** (`timed_out=True`, tree-killed) — **~200 ms kill overhead**, did not hang 30 s |
| **Wedge/timeout (network)** | the pc2 SSH attempt above | bounded at **10.18 s** by `ConnectTimeout` — remote half of the anti-wedge, fast-fail not hang |

**Two live findings worth acting on (both honest, both new):**
1. **Node-selection trusts stale capability state.** `route()` cheerfully selected **`pc2/codexA`** for an
   offload job because `capabilities.json` still marks that cell green — even though pc2 is provably offline
   right now. The router only excludes a node if it is in the DB *cooldown/unreachable* set; with **no fresh
   reachability probe feeding that set**, a dead node stays selectable. A probe-before-route (or a shorter
   cooldown TTL) would have moved pc2 to `unavailable`. Measured staleness gap, not a code-read guess.
2. **The consensus gate already does the "differentiator-OFF" honesty I recommended (★5).** With codex+agy
   out of quota, a single-vendor panel returns **`cannot_form_quorum`** with a named reason, not a silent
   pass — exactly the graceful degradation the adopt-list asked for. That primitive exists; what's missing is
   wiring it to *vendor-quota detection* so the router stops routing to a dead lane in the first place.

**Net effect on the scorecard:** the multi-PC row moves from *code-read only* to **plumbing live-verified on a
2-node cluster**: transport (SSH exec), routing, fan-out, consensus-or-flag, and both halves of the anti-wedge
timeout are **measured working today**; only the vendor-completion step is quota-blocked, and pc2 is down. The
"AHEAD on cross-vendor consensus-or-flag" verdict stands on prior A/B/C evidence; the *live* addition is that
the orchestration substrate underneath it is proven, fast (sub-ms routing/fan-out), and fail-safe.

---

## 2. The six-axis frontier scan (technique → paper → do we do it?)

| # | Axis | Frontier technique + source | Do we do it? | Adopt? |
|---|---|---|---|---|
| 1 | **Orchestration / routing** | Supervisor topology + durable graph w/ checkpoint-resume (LangGraph); task/progress ledger (Magentic-One); cost-aware cascade (RouteLLM, AdaptOrch arXiv:2602.16873) | Capability-routing + anti-wedge coordinator ✅; **no durable graph/checkpoint** ❌; **no learned cost router** ❌ | Durable checkpoint-resume for multi-day lanes (M); learned vendor router (M) |
| 2 | **Verification / judging / consensus** | Trained robust verifier (CompassVerifier `[PEER]` 2508.03686); master-key + token-space attacks (2507.08794, 2604.02686); enforced-family panels, effective votes (2605.29800); CoT+rubric (2604.23178); **conformal abstention** (CAP `[PEER]` PMLR v304; ToolChain-CRC 2606.18467) | Degenerate guard ✅, CoT default-on ✅, enforced-family quorum ✅, injection guard ✅, effective-votes ✅, **conformal abstain gate landed** ✅; **no trained verifier** ❌ | ★ Learned-verifier witness tier (L); harden the clean-boundary leak via typed tool-call output (S) |
| 3 | **Agent memory** | Temporal KG (Graphiti, LongMemEval 63.8%); Zettelkasten A-MEM (2502.12110); sleep-time compute (2504.13171); **optical memory** OCR-Memory (2604.26622) | Temporal validity ✅, decay ✅, source-hash ✅, dream-consolidation ✅, claim-graph retraction ✅; **no entity graph** ❌; **never LongMemEval'd** ❌; markdown layer unbridged ❌ | Bridge markdown↔SQLite temporal metadata (S); run LongMemEval to get a real recall number (M) |
| 4 | **AI-code safety gates** | Semantic/dataflow AI-SAST vs regex ([Augment]); VibeGuard security gate (2604.01052, 100%R/89.5%P); SLSA provenance + signed attestation ([Cloudsmith]) | Diff-scoped gate ✅, fabrication family ✅ (rare), hash-chained bypass ✅; **regex-dominant** (42/64) ⚠️; **no SLSA/attestation** ❌; **manifest drifting** ⚠️ | ★ Move hot rules to AST/semgrep-class (M); sign the rule manifest + fix drift (S); measure Sentinel P/R (S) |
| 5 | **Reproducibility / eval harness** | Inspect AI `[GOV/OSS]`; SpecBench held-out gap (2605.21384); **Harness-Bench** (2605.27922) — 23.8pt harness-config gap, "report at model×harness level"; container-digest + `PYTHONHASHSEED` + temp=0 determinism; SWE-bench Pro (contamination fix); UTBoost (2506.09289) | Objective-witness floor ✅, numerical baselines ✅, held-out policy ✅, **private reconstruction corpus** ✅✅, 13 evals ✅; **evals are fixtures not live** ⚠️; **not on Inspect AI** ❌ | ★ Live-model eval pass (M); adopt Inspect's failure→eval→CI loop (M) |
| 6 | **Heterogeneous / cross-vendor ensembles** | Co-failure ceiling 1−β (2606.27288): low-ρ heterogeneous > high-ρ; MoA/Mixture-of-Models (2406.04692, 2601.16863); routing needed on checkable tasks | Cross-family consensus-or-flag ✅, effective-votes ✅, enforced families ✅, **measured A/B/C two-slice** ✅✅; **vendor reliability fragile** ⚠️ | Quota-aware vendor routing + graceful "differentiator-OFF" flag (M) |

---

## 3. Ranked "adopt now" list (value ÷ effort, truth-first). ★ = top 5

| Rank | Technique → paper | Component | Effort | Expected gain |
|---|---|---|---|---|
| **★1** | **Live-model eval pass** — run A/B/C + reconstruct-and-beat + judge master-key against *real* claude/codex/agy, publish live numbers (turns "logic proven" → "accuracy proven"). *SpecBench 2605.21384; our fixtures.* | Overmind, cluster | **M** (gated on vendor quota) | Converts every fixture verdict into a defensible live number; **precondition for any "world-class" claim** |
| **★2** | **Learned-verifier witness tier** — add a CompassVerifier-class trained verifier as an *optional objective witness*, escalate to it when the regex guard is uncertain. *arXiv:2508.03686 `[PEER]`; token-space attacks 2604.02686.* | Overmind (judge) | **L** | Hardens the judge past regex guards; directly attacks the token-space/master-key attack surface the guard can't fully cover |
| **★3** | **Move Sentinel's hot rules to AST/semantic + sign the manifest** — port `unsafe_eval_exec`, `leaked_secret`, `insecure_deserialization` from regex to AST/semgrep-class; sign `rules-manifest.json`; fix the current DRIFT. *AI-SAST semantic 2026; VibeGuard 2604.01052.* | Sentinel | **M** | Closes the "evadable regex" gap on the highest-risk rules; makes the integrity guarantee cryptographic, not honor-system |
| **★4** | **Confirm the conformal abstain gate on live data** — the gate landed (flips the FAR clause NOT_PROVEN→WORLD_CLASS on fixtures); verify it holds on a real cross-vendor run and expose the risk–coverage curve. *CAP `[PEER]` PMLR v304; Conformal Selective Acting 2605.20270; ToolChain-CRC 2606.18467.* | Overmind, cluster | **S** (code exists) | Calibrated, finite-sample false-alarm control — the last clause between "caught-defect win" and a clean WORLD_CLASS verdict |
| **★5** | **Quota-aware vendor routing + graceful "differentiator-OFF" flag** — detect cap/degradation per vendor; route to a live ≥2-family panel when possible; when only one family is live, **flag "single-vendor, consensus-or-flag OFF"** instead of silently degrading. *Co-failure ceiling 2606.27288; codex-seat-ops / agy-driver.* | Dispatch, cluster | **M** | Directly attacks the binding constraint (vendor reliability); prevents a degraded run from masquerading as a heterogeneous check |
| 6 | Durable checkpoint-resume for multi-day lanes (LangGraph-style) | Dispatch | M | Wedged lanes resume a node, not restart |
| 7 | Bridge markdown↔SQLite temporal metadata; run LongMemEval | Memory | S/M | One coherent memory with a real recall number |
| 8 | Adopt Inspect AI's *production-failure → eval-case → CI-gate* loop | Overmind | M | Standardizes the eval loop without a full framework migration |
| 9 | Promote objective-gate from shadow/WARN to blocking in the general orchestrator path | Overmind | S | Makes the objective floor hard everywhere, not just the typed path |
| 10 | Real container/microVM isolation for untrusted remote witnesses (replace the STUB) | cluster | L | Only material if we ever verify third-party/agent-generated code at scale |

---

## 4. The north-star verdict — is the harness world-class *for its purpose?*

**Purpose (from `WORLD_CLASS_SPEC.md`):** *best-in-the-world at truth-gated, cross-vendor
reproduction-and-verification of quantitative evidence-synthesis work — provably.* Not "a good agent framework."

**Verdict: YES on architecture and on three measured differentiators — but with a live-fuel asterisk, not
yet a clean sweep.** The honest state is "**world-class-by-construction and by fixture-eval; world-class-by-live-
measurement is one vendor-quota window away.**"

**What genuinely earns the claim (measured, ahead of the published frontier):**
1. **Cross-vendor consensus-or-flag with a *measured, two-slice* heterogeneity benefit** — Arm C (0.921) beats
   single-agent A (0.802) *and* homogeneous-triple B (0.770), with B<A proving the win is heterogeneity not
   votes. This independently reproduces the co-failure-ceiling result (arXiv:2606.27288) on our own corpus.
   **Published panels almost never demonstrate this.**
2. **Objective truth-gate + fail-closed UNVERIFIED as the architecture**, now eval-backed (`reward_hack` catch
   100%/5-of-5, `degenerate` 0%, `specbench_gap` 33.3% published) — not asserted, measured.
3. **A private reproduction ground-truth corpus** — `reconstruct_and_beat` reconstructs 7 published
   meta-analyses from open data and validates against R/metafor to ≤1e-4 (honest headline: *match* on point
   estimates, *beat* on uncertainty calibration/transparency — e.g. an HKSJ small-k correction flips one
   published significance). Plus AACT registered-vs-published. **This is the moat: an eval nobody else can
   score against**, and it closes the June "nothing is measured" gap.

**What keeps it honest (the 3-5 upgrades that would make it *defensibly* world-class):**
1. **Live-model measurement** (adopt-list ★1). Every number is fixture-based today; the differentiator's real
   accuracy is proven only on prior degraded runs. A clean live A/B/C + reconstruct-and-beat pass, published,
   is the precondition for the unqualified claim.
2. **Vendor-reliability layer** (★5). The differentiator is *paused* whenever <2 families are live — which is
   often. Quota-aware routing + explicit differentiator-OFF flagging turns an intermittent moat into a
   dependable one.
3. **Confirm the conformal FAR gate on live data** (★4) — the last clause between "caught-defect win" and a
   clean WORLD_CLASS verdict.
4. **A learned-verifier tier** (★2) — to claim robustness against the token-space/master-key attack frontier,
   not just the degenerate cases the regex guard covers.
5. **Close the two structural half-measures** — the injection clean-boundary leak (typed tool-call output) and
   the objective-gate being WARN-only in the general path (promote to blocking).

**Bottom line:** For its narrow, well-chosen purpose the harness is **at or beyond the published frontier on
the things that define that purpose** (cross-vendor truth-gating, reproduction ground-truth, fail-closed
verification), and it is honest about the rest. It is **not** a general agent framework and shouldn't be
marketed as one. The one thing standing between "world-class by construction" and "world-class, proven" is a
**live cross-vendor eval run** — which is exactly what today's quota outage blocks.

---

## 5. Where we're already ahead of the published frontier (worth claiming)

1. **Measured heterogeneity-beats-homogeneity, two-slice confirmed.** The co-failure-ceiling paper
   (arXiv:2606.27288) is a mid-2026 *preprint*; we have working cross-family consensus-or-flag **plus our own
   corpus reproducing its central finding** (B<A; heterogeneity, not votes, is the source of gain; 3rd-vendor
   diminishing returns). Enforced-family quorum + surfaced effective-votes is rarer still in production.
2. **Claim→evidence retraction propagation, shipped and eval-proven.** *Grounded Continuation*
   (arXiv:2605.14175) is a preprint; our `claim_graph.py` + `MemoryStore.propagate_retraction()` is running
   code with a measured transitive-recall 33%→100%.
3. **Objective-witness floor + first-class UNVERIFIED verdict.** Fail-closed abstention as *architecture* (a
   SKIP-on-missing-baseline can never become CERTIFIED) is ahead of typical LLM-judge deployments and matches
   exactly the abstention/calibration direction the 2026 judge-security literature is converging on.
4. **A private reproduction ground-truth corpus** (reconstruct-and-beat vs published MAs + R/metafor parity,
   AACT registered-vs-published). General harnesses benchmark on public SWE-bench/GAIA; a *domain* ground-truth
   corpus nobody else holds is a structural moat.
5. **Signed, replay-protected, immutably-scoped verdicts + hash-chained bypass audit.** Stronger provenance
   *discipline* than most personal or even many production stacks — behind only on standards-based supply-chain
   attestation (SLSA), which is an add-on, not a correctness gap.

---

## 6. Rails, limitations, and source maturity

**Rails honored:** report-only / staged; committed ff-only to a non-rapidmeta repo (`overmind`), nothing
deployed; **no rapidmeta repo touched** (rapidmeta-staging / rapidmeta-finerenone left frozen). Every claim
carries a real citation; preprint numbers are marked as *their* measurements, not ours.

**Limitations of this benchmark (honest):**
- **Cross-vendor verification could not be exercised live today** (Codex + agy out of quota; headless Claude
  has no non-interactive path). All cross-vendor numbers are prior-run, not re-verified — flagged, not faked.
- **All 13 eval numbers are fixture-based** (deterministic seeded/stub panels), proving harness *logic*, not
  live-vendor accuracy; two are saturated at the fixture ceiling.
- **`ContainerIsolation.run_in_container()` is a STUB** (always SKIP) — the untrusted-must-isolate *gate* is
  real, the isolation *runtime* is not.
- **Sentinel's rule manifest is drifting right now** (1 modified rule, un-regenerated) and is **unsigned**.
- **Markdown and SQLite memory are unbridged** — the markdown layer has no temporal metadata.
- The `frontier-closing-2026-06-24` branch reached master by an **indirect path** (rebase/cherry-pick, not a
  named merge) — modules confirmed present on master, exact mechanism **UNVERIFIED**.

**Source maturity:**
- **Primary / strongest:** CompassVerifier `[PEER, EMNLP 2025]`, Inspect AI `[GOV/OSS]`, CAP `[PEER, PMLR]`,
  Anthropic engineering pages, the LLM-as-a-Judge Security SoK.
- **Directional preprints (adopt the idea, validate the number ourselves):** co-failure ceiling (2606.27288),
  Harness-Bench (2605.27922), SpecBench (2605.21384), OCR-Memory (2604.26622), VibeGuard (2604.01052),
  token-space attacks (2604.02686), Grounded Continuation (2605.14175), Nine-Judges (2605.29800).
- **Orientation only (not cited as fact):** vendor "best-of-2026" listicles, LongMemEval win-rates, harness
  overhead percentages — directional magnitudes, verify before quoting.

*Scores shipped code as of 2026-07-10 (branch `reconstruct-and-beat-2026-07-10`, HEAD `a5236e3`). Re-run after
a live cross-vendor eval pass — several "at-par-by-fixture" calls should become "ahead-by-live-evidence."*
