# TRINITY (arXiv 2512.04695, Sakana AI, ICLR 2026) — empirical validation

**URL:** https://arxiv.org/abs/2512.04695 (HTML https://arxiv.org/html/2512.04695v3 ; https://sakana.ai/trinity/ )
**What:** a tiny evolved coordinator routes sub-steps to a pool of frontier models, looping until a
Verifier accepts. Strongest empirical validation of our conductor + maker/checker architecture.

## VERIFIED (fetched paper)
- Coordinator = **0.6B params + ~10K head** (<20K learnable). It **routes, doesn't answer.**
- Per turn assigns **Thinker / Worker / Verifier** to a selected LLM.
- **New SOTA 86.2±0.5% LiveCodeBench**, beating GPT-5 (0.838), Gemini 2.5-Pro (0.672), Claude-4-Sonnet
  (0.465); zero-shot transfer to AIME/BigCodeBench/MT-Bench/GPQA.
- **Acceptance-driven loop:** terminates when Verifier ACCEPTs (`τ = min{k≤K: Rk=V and uk=ACCEPT}`).
- → validates: team beats single (a); check-before-ship is central (c); router need not be biggest (d-weak).

## REPORTED / UNVERIFIED (NOT in the paper)
- **"Top-tier model as manager made it WORSE"** — paper NEVER varies coordinator size (ablations are
  component-only). Cheap-router = cost lever is motivated by 0.6B-suffices, but "bigger = worse" is
  reported-not-verified.
- **"Verifier must be a different model"** — paper does NOT mandate Worker≠Verifier. We keep this as
  **our own** `enforce_distinct_families` / reviewer≠writer rule, reinforced by (not derived from) TRINITY.
- Related (not fetched): Sakana **Fugu**, Microsoft **Terminus-4B**.

## Ties to
Our T-CV cross-vendor check · cheap-router cost lever · [[src-evolve-the-harness]].
