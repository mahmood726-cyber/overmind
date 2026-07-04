# AutoMem (arXiv 2607.01224, Stanford) — HIGH RELEVANCE (memory ⨯ harness-evolution)

**URL:** https://arxiv.org/pdf/2607.01224 · Stanford.
**What:** reframes agent memory from an **engineering problem** (which vector DB / retrieval algo) into a
**learnable cognitive skill** — memory decisions (when to store, what to store, how to retrieve) live in the
**same action space as task actions**, trained end-to-end.
**Why it matters:** the most on-point recent paper — it **bridges two of our themes** (agent-memory +
[[src-evolve-the-harness|evolve-the-harness]]) and argues our vault/MemClaw/SOP layer should not sit static.

## The structure (as recorded from the brief)
- **Two NESTED LOOPS:** an **outer meta-loop** optimizes the memory **ARCHITECTURE**; an **inner loop**
  trains a dedicated **"memory-skill" model distilled from the agent's own execution trajectories.**
- Starting from a base agent with **filesystem memory**, the two stages (memory-architecture optimization →
  memory-skill training) give **continuous gains.**

## Maps to us (explicit)
1. **Outer meta-loop = harness-evolution applied to MEMORY** — the same shape as Niklaus
   ([[src-evolve-the-harness]]) and our checklist's **shared-store** item, but the thing being evolved is the
   *memory policy* itself.
2. **Nested-loop structure mirrors the LFD inner/outer loops** ([[src-lfd]]): inner = make it work on the
   trajectory; outer = descend an outcome metric over the memory architecture.
3. **Our vault / MemClaw / SOP layer shouldn't be STATIC** — the "manage your own memory" policy should
   **evolve with task experience** (distilled from our own runs), not be hand-fixed once.

## ⚠ Truth-first caveat
It is a **research training method** (an end-to-end *trained* memory-skill), so it is **not directly
adoptable as-is.** The **transferable principle** is the framing: **memory decisions as first-class,
learnable/evolvable, distilled from the agent's own trajectories.** We adopt the framing, not the training
pipeline.

## Tier
**Actionable-adjacent** (transferable framing, not a drop-in technique). Cross-filed under **both** the
memory theme and the **harness-evolution** theme.

## Ties to
[[src-evolve-the-harness]] (outer meta-loop = evolve the harness, applied to memory) · [[src-lfd]]
(nested inner/outer loops) · [[src-memclaw]] (the store this would learn to manage) ·
[[src-hippocampus-linear-attention]] (the exact-vs-compressive split it would learn to route) · [[Home]].
