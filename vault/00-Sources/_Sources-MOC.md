# Sources — MOC (external sources reviewed 2026-07-04)

Structured, annotated index of the external material reviewed today, grouped by theme. Each entry: what it
is + one-line **why it matters / how it maps to us**. Full per-source notes carry verified facts and
truth-first flags. Every URL is collected in [[reference-library]].

> **Truth-first convention:** each source note separates **VERIFIED** (fetched the page/repo/paper today)
> from **REPORTED / UNVERIFIED** (attributed anecdotes, marketing, or claims I could not confirm). Where a
> paper's PDF would not yield a specific number, the claim is qualitative and flagged.

## harness-evolution — *hold the model fixed, evolve the harness*
- [[src-evolve-the-harness]] — **Joel Niklaus, "Don't Train the Model, Evolve the Harness."** The
  centerpiece framing: an automated, benchmark-gated loop that mutates the harness around a fixed model.
- [[src-trinity]] — **TRINITY (Sakana AI, ICLR 2026).** Empirical proof the shape works: a 0.6B coordinator
  routing Thinker/Worker/Verifier across a model pool, looping until a Verifier accepts, beats every
  individual frontier model. Validates our conductor + maker/checker gate.
- [[src-automem]] — **AutoMem (Stanford, arXiv 2607.01224).** *Cross-filed with memory.* Harness-evolution
  applied to **memory**: an outer meta-loop evolves the memory architecture, an inner loop trains a
  memory-skill from the agent's own trajectories. **HIGH — actionable-adjacent** (framing, not a drop-in).

## loop-anatomy — *the shape of a good loop*
- [[src-loop-engineering-cherny]] — **Boris Cherny, "build loops, not prompts."** The three load-bearing
  parts (objective VERIFY gate · external STATE · STOP condition); names our biggest gap.
- [[src-loop-library]] — **Forward Future Loop Library.** Curated loop templates, each with an explicit
  STOPPING CONDITION — the concrete shapes for our lanes.
- [[src-ai-edge-loop-guide]] — **AI Edge (@aiedge_) guide + Fable-5.** The `/loop`+`/goal` template and
  6-part loop anatomy; commands verified against the docs.
- [[src-lfd]] — **Elvis Sun, Loss-Function Development (`/goal` loss functions).** How to design the loss
  the outer loop descends and fence it against reward-hacking.
- [[src-right-in-the-right-way]] — **"Right in the Right Way" (MIT, arXiv 2607.01181).** *Anti-reward-hacking.*
  A training paper whose finding transfers: scoring only the verifiable signal produces reward hacking;
  complement it with a harder-to-game signal. **MED — actionable-adjacent** (insight, not a technique).
- [[src-scheduler-graph-sgh]] — **Scheduler-graph / SGH (arXiv 2604.11378).** The execution substrate
  (DAG scheduling, bounded escalation, `any_of` racing). ⚠ position paper, concepts only.
- [[src-claude-code-docs]] — **Claude Code docs.** The real primitives every mechanism is built from
  (subagents, hooks, headless `-p`, skills, MCP).

## benchmarking — *how a mechanism earns its keep*
- [[src-made-benchmark]] — **MADE (arXiv 2601.20996).** Closed-loop benchmark under a constrained oracle
  budget → the design analogy for our Evaluator (efficacy + cost-per-accepted-change vs a baseline).

## skills — *reusable, auditable agent knowledge*
- [[src-mattpocock-skills]] — **mattpocock/skills.** Patterns to adapt for our lane skills (tdd, code-review,
  diagnosing-bugs, triage).
- [[src-sanyuan-skills]] — **sanyuan0704/sanyuan-skills.** Production skills + the meta-tooling (Skill
  Forge/Review, Wiki Ingest) to author + audit our own. ⚠ audit third-party skills before install.

## memory — *the shared store*
- [[src-memclaw]] — **Caura MemClaw.** MCP-native governed shared memory for agent fleets — the machine
  layer that this vault (the human layer) mirrors.
- [[src-automem]] — **AutoMem (Stanford, arXiv 2607.01224).** *Cross-filed with harness-evolution.* Memory
  decisions as a first-class, **learnable/evolvable** skill distilled from the agent's own trajectories —
  argues our vault/MemClaw/SOP layer shouldn't sit static.
- [[src-hippocampus-linear-attention]] — **HOLA / "A Hippocampus for Linear Attention" (arXiv 2607.02303).**
  *Design metaphor only (also a background paper).* Its compressive-state + bounded-exact-cache split
  mirrors our **MemClaw (semantic) + exact audit/verification store** design. **Analogy, not a technique.**

## tools — *candidate adoptions (link/tools library)*
- [[tool-ragas]] — **Ragas** eval framework (faithfulness / context precision) — objective-ish gate for the
  LLM-mediated extraction lanes. **MED-HIGH, actionable.**
- [[candidate-tools-weekend-repos]] — 10 weekend repos resolved + triaged (High→None + security); top picks
  ComposioHQ/agent-orchestrator, oh-my-claudecode, Hermes-agent; **AVOID: ST3GG**.

## Background reading — *pure-ML-theory, NOT actionable*
Kept deliberately separate so the adoptable sources stay clean. Nothing here is a technique to adopt.
- [[src-attention-residuals-excluded]] — **Attention Residuals (Kimi Team, arXiv 2603.15031).** A
  train-the-model technique — assessed and **excluded** (the counterpoint to "evolve the harness").
- [[src-hippocampus-linear-attention]] — **HOLA (arXiv 2607.02303).** Architecture paper; kept only for its
  memory-design *metaphor* (see the memory theme).
- [[src-diffusion-models-intro]] — **A Mathematical Introduction to Diffusion Models (arXiv 2607.01693).**
  Graduate lecture notes; **reference-only**, loose tangent to the MinerU-Diffusion OCR decoder.

---

## Source tiers (actionable / actionable-adjacent / background)
| Tier | Sources |
|---|---|
| **Actionable** — adopt / build from now | [[src-evolve-the-harness]] · [[src-loop-engineering-cherny]] · [[src-loop-library]] · [[src-ai-edge-loop-guide]] · [[src-lfd]] · [[src-scheduler-graph-sgh]] · [[src-claude-code-docs]] · [[src-made-benchmark]] · [[src-trinity]] · [[src-mattpocock-skills]] · [[src-sanyuan-skills]] · [[src-memclaw]] · **tools:** [[tool-ragas]] · [[candidate-tools-weekend-repos]] |
| **Actionable-adjacent** — transferable framing/insight, not a drop-in | [[src-automem]] (memory as a learnable/evolvable skill) · [[src-right-in-the-right-way]] (reward-hacking is real; complement the objective gate) |
| **Background** — pure-ML-theory, reference-only | [[src-attention-residuals-excluded]] · [[src-hippocampus-linear-attention]] · [[src-diffusion-models-intro]] |
