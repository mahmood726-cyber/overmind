# MADE (arXiv 2601.20996) — closed-loop benchmark = our Evaluator

**URL:** https://arxiv.org/abs/2601.20996 (HTML https://arxiv.org/html/2601.20996v1 )
**What:** benchmarks agentic pipelines as **closed-loop campaigns under a constrained oracle budget**,
with composable components + ablation, scored on efficacy AND efficiency vs a baseline.
**Truth-first:** materials-discovery domain — a **transferable design analogy**, NOT a methods/LLM result.
None of its numbers claimed for us.

## VERIFIED (fetched HTML)
- Oracle budget `B∈ℕ`; experiments use **50 queries/episode × 5 episodes**.
- Components: **Planner / Generator / Filter / Selector** (interchangeable); component ablation.
- Metrics: **mSUN** (frac. metastable/unique/novel), **AUDC** (area under discovery curve); relative:
  **AF (Acceleration Factor)**, **EF (Enhancement Factor)** vs a **random-generator baseline**.
- Ablation headline: Chemeleon+MLIP **AF = 6.4** vs random 1.0.

## Mapped to our harness benchmark (Step 6)
budget = token/$ cap · components = maker/checker/verifier arms · ablation = Claude-only vs +Codex vs +agy
vs full quorum · efficacy = agreement/caught-bug rate · efficiency = cost-per-accepted-change · baseline =
single-agent. This is the **Evaluator** of the [[src-evolve-the-harness]] loop, with [[src-lfd]]'s
promotion rule on top.

## Ties to
[[src-evolve-the-harness]] · [[src-lfd]] · [[src-trinity]].
