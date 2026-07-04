# Hippocampus for Linear Attention / HOLA (arXiv 2607.02303) — memory design METAPHOR

**URL:** https://arxiv.org/abs/2607.02303 · Wanyun Cui. *A Hippocampus for Linear Attention.*
**What:** an **LLM architecture** paper. HOLA gives linear-attention / state-space models a **bounded EXACT
KV cache** (a "hippocampal" complement) alongside the lossy compressive recurrent state, so exact key-value
facts aren't overwritten — better long-context needle recall, lower perplexity.

## ⚠ Relevance call (honest): NOT directly applicable — ANALOGY only
This is **model-internal architecture**, not our orchestration harness or evidence-synthesis methods. It
would only be directly relevant **if we trained our own models** (not on any roadmap). Filed here as a
**design metaphor, not a technique to adopt.**

## The conceptual analogy worth recording (memory theme)
HOLA's split — **compressive state + a bounded exact cache** (framed as Complementary Learning Systems) —
**mirrors the agent-memory design we discussed:**
- a **self-improving semantic/compressive recall layer** = MemClaw retrieval ([[src-memclaw]]) —
  lossy, learned, good for "what's roughly relevant";
- **PLUS an exact, never-lossily-summarized audit/verification store** = our audit trails, the verification
  reports ([[_Verification-MOC]]), and **exact numbers** (κ = `0.1575949114447188`, the frozen deploy
  values) — facts that must survive verbatim, never be paraphrased by a summarizer.

The lesson the metaphor reinforces: **don't let the compressive layer be the only memory.** A truth-first
research harness needs the "hippocampal" exact store next to the semantic one — which is exactly the
vault (human exact) + MemClaw (machine semantic) split, and why the [[Single-Writer-Rule-SOP]] keeps frozen
numbers write-once.

## Tier
**Background reading (pure-ML-theory)** — grouped with [[src-attention-residuals-excluded]] and
[[src-diffusion-models-intro]]. Actionable only as the memory-design metaphor above.

## Ties to
[[src-memclaw]] · [[src-automem]] (learnable memory) · [[_Verification-MOC]] (the exact store) ·
[[src-attention-residuals-excluded]] (fellow architecture paper).
