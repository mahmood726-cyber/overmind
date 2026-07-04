# Scheduler-Graph / SGH (arXiv 2604.11378) — execution substrate

**URL:** https://arxiv.org/abs/2604.11378 · HTML https://arxiv.org/html/2604.11378
**Author:** Hu Wei. *From Agent Loops to Structured Graphs: A Scheduler-Theoretic Framework for LLM Agent Execution.*
**What:** unifies "agent loop" and "graph engine" on one axis and models execution as a scheduled DAG.
**Why it matters / how it maps to us:** it is the *execution substrate* the evolved harness would run on —
dependency-aware routing, bounded recovery, and cross-vendor racing for the three colliding "dispatch"
concepts in our stack.

## ⚠ Truth-first — this is a POSITION PAPER
The paper states up front it has **"no production implementation or empirical results."** Its predicted
gains (`G_graph`, `G_plan`, `G_replan`) are "logical consequences of the framework's assumptions," **not
measured.** We adopt its *concepts only* — never cite its predicted gains as fact.

## VERIFIED (concepts, from the paper)
- **The unifying axis:** an agent loop = a "single-ready-unit scheduler" (`|𝒰| ≤ 1`, next unit chosen by
  opaque LLM inference); a graph harness = a static DAG with a **deterministic scheduler** (`|𝒰| ≥ 1`)
  over nodes (tool calls / sub-tasks) + dependency edges.
- **Join semantics:** `all_of` (constructive parallelism — wait for all branches) and `any_of`
  (competitive parallelism — first success wins).
- **Three-level escalation recovery:** L1 bounded Retry (transient) → L2 Local Patch (reasoning error) →
  L3 Replan; the paper argues this "prevents unbounded recovery loops."
- **Immutable, versioned plans:** planning / execution / recovery in three layers, "no mutable execution
  history that complicates debugging."
- Worked example: an 11-sequential-turn agent loop → 6 scheduling rounds via parallel waves.

## Maps to our systems (concept-adoption path)
- `cluster/delta_skip.py`'s `ContractImpactGraph` is already a repo-dependency graph → lift into DAG edges
  for **dependency-aware routing** (run a repo's dependents only after it passes).
- The escalation protocol **formalizes + bounds** what [[Cross-Vendor-Witness-SOP|T1/T6]] do piecemeal
  (L1 = watchdog retry, L3 = replan) with an explicit ceiling that stops requeue storms.
- `any_of` = the shape of a **cross-vendor quorum race** (dispatch the same verification to Codex/agy/Claude,
  take the first sound verdict).
- Immutable versioned plans = the design rationale under a durable dispatch journal; a plan pinned to
  node/data-locality is what prevents the "sandbox-can't-reach-F:" mis-route.

## Safe adoption (from the research doc, T10)
Concept-adoption, not framework-adoption: (1) bounded escalation protocol first; (2) `ContractImpactGraph`
→ explicit DAG edges behind a flag, shadow-compared for identical verdicts; (3) plan-immutability as a
north-star realized incrementally. **Do not** rip out the working loop for the paper's theoretical
parallelism.

## Ties to
[[src-evolve-the-harness]] (substrate for) · [[src-loop-library]] (`any_of` racing) · [[Gated-Additive-Deploy-SOP]].
