# Right in the Right Way (arXiv 2607.01181, MIT) — MEDIUM relevance (anti-reward-hacking)

**URL:** https://arxiv.org/abs/2607.01181 · Damani, Puri, Shenfeld, Andreas (MIT).
*LM Training with Verifiable Rewards and Human Demonstrations.*
**What:** a **model-training** paper — RLVR (RL with verifiable rewards) + an **adversarial
generator–discriminator** trained with **human demonstrations.**
**Why it's MEDIUM, not not-applicable:** the *method* isn't ours to adopt, but its **core finding directly
reinforces our workflow thesis** about objective gates and reward hacking.

## The finding that transfers
- RL/optimization that scores **only the objectively-verifiable** signal **neglects non-verifiable
  quality** and produces documented **reward hacking, diversity collapse, and unnatural outputs.**
- **Augmenting the verifiable reward with a learned human-demonstration signal "nearly eliminates reward
  hacking while maintaining benchmark scores."**

## Maps to us (transferable INSIGHT, not a technique)
- Reinforces [[src-lfd]] (Elvis Sun): *the agent is an optimizer; every cheap path you don't fence off is a
  direction it sprints down* — it games the metric. This paper is independent evidence that **reward hacking
  is real** and shows, in principle, **how to counter it** (add a harder-to-game, human-aligned signal).
- Reinforces our **objective-gate design** ([[Gated-Additive-Deploy-SOP]], the checklist's T12a): an
  objective gate is **necessary but a single scalar gets gamed** — so **complement** it with a
  harder-to-game signal. For us that complement is the **cross-vendor / human-aligned check**
  ([[Cross-Vendor-Witness-SOP]]), not a learned discriminator.
- Live examples of the failure this warns about: our `compound_judge` empty-steps → pass, low-confidence
  FAIL-as-PASS, `injection_clean_boundary` 100% false-PASS, RapidMeta `cE>cN` at scale
  ([[RapidMeta-Repool-Findings]]).

## ⚠ Honest framing
**Transferable insight** (reward hacking is real + how to counter it in principle), **not a
directly-adoptable technique** (we are not RL-training a model). Do not cite its numbers as ours.

## Tier
**Actionable-adjacent** — loop-engineering / anti-reward-hacking theme.

## Ties to
[[src-lfd]] (fence the cheap paths) · [[Cross-Vendor-Witness-SOP]] (the harder-to-game complement) ·
[[Gated-Additive-Deploy-SOP]] (objective-gate design) · [[src-loop-engineering-cherny]].
