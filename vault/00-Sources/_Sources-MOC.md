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
- [[src-attention-residuals-excluded]] — **Attention Residuals (Kimi Team).** The *counterpoint*: a
  train-the-model technique, **assessed and deliberately excluded** — no bearing on orchestration.

## loop-anatomy — *the shape of a good loop*
- [[src-loop-engineering-cherny]] — **Boris Cherny, "build loops, not prompts."** The three load-bearing
  parts (objective VERIFY gate · external STATE · STOP condition); names our biggest gap.
- [[src-loop-library]] — **Forward Future Loop Library.** Curated loop templates, each with an explicit
  STOPPING CONDITION — the concrete shapes for our lanes.
- [[src-ai-edge-loop-guide]] — **AI Edge (@aiedge_) guide + Fable-5.** The `/loop`+`/goal` template and
  6-part loop anatomy; commands verified against the docs.
- [[src-lfd]] — **Elvis Sun, Loss-Function Development (`/goal` loss functions).** How to design the loss
  the outer loop descends and fence it against reward-hacking.
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
