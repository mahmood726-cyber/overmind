# Attention Residuals (arXiv 2603.15031) — ASSESSED AND EXCLUDED

**URL:** https://arxiv.org/abs/2603.15031 · Kimi Team.
**What:** an **LLM pretraining-architecture technique** — replaces standard PreNorm residual connections
with **softmax attention over preceding layers' outputs**, so each layer selectively aggregates earlier
representations with learned, input-dependent weights. A **Block AttnRes** variant attends over
block-level representations to cut memory, as a "drop-in replacement for standard residual connections."
Integrated into **Kimi Linear** (48B total / 3B activated) to mitigate PreNorm dilution and even out
gradient magnitudes across depth.

## ⚠ Honest verdict: NOT APPLICABLE to our orchestration stack
It operates **inside model training internals** — not agent orchestration, tool use, or inference-time
workflows. **Zero bearing on Sentinel / Overmind / the harness / Dispatch.** The only way it would matter
is if we ever pretrained or heavily fine-tuned our own base model, which is not on any roadmap here.

Kept in the vault for **completeness** and as the deliberate **counterpoint** to the through-line: Niklaus
([[src-evolve-the-harness]]) says *evolve the harness, not the model*; Attention Residuals is exactly a
*train-the-model* technique — so it is documented and **deliberately excluded** from the adoptable
shortlist, so we don't shoehorn a training-time idea into a workflow problem.

## Provenance
Assessed 2026-07-04 in the workflow research doc (§5), which reached the same exclusion verdict. Only the
scheduler-graph paper ([[src-scheduler-graph-sgh]], 2604.11378) is directly workflow-relevant among the
two arXiv architecture papers reviewed.

## Ties to
[[src-evolve-the-harness]] (the excluded counterpoint to "evolve the harness").
