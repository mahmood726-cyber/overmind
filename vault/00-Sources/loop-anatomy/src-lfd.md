# Loss-Function Development (Elvis Sun) — loss design + anti-reward-hacking

**URL:** https://github.com/elvisun/loss-function-development (the `/lfd-design` skill). Relays Peter
Steinberger's "design loops that prompt your agents."
**What:** how to design the *loss* the outer [[src-evolve-the-harness|harness-evolution]] loop descends,
and how to fence it against reward-hacking.

## VERIFIED (fetched repo)
- Public repo, **155★ / 9 forks**. `/lfd-design` "designs loss functions for long-running autonomous
  agent loops."
- **LFD vs spec-driven:** "make the tests pass" (inner loop, DONE when green) vs "then iterate against a
  thousand eval cases you can't see" (outer loop, a target you descend). Two nested loops = gradient
  descent all the way down.
- **4-part loss:** (1) TARGET (large enough no-enumeration; blinded; measured mechanically at right
  resolution), (2) CONSTRAINTS (wall-clock/budget/surface/methodology/capacity), (3) INSTRUMENTS ("a
  constraint without an instrument is a vibe"; ship a CLI per constraint), (4) FORCED ENTROPY (overfit
  reflection, stall rules, exploration quotas; the skill keeps a "cheat museum" + red-teams its drafts).
- **Reward-hacking (headline):** "the agent in the loop is an optimizer, and every cheap path you don't
  fence off is a direction it will sprint down. It will memorize your eval, mine your miss-lists into
  lookup tables, and game your judge."
- **MOAT insight:** "the product is a weekend now; the eval nobody else can score against is the moat."
  → our private ground truth (AACT registered-vs-published, gold MA library, truth-gated reproduction).

## REPORTED / UNVERIFIED
- "50× / 30 hours / $40" and "agent cheated 3×" — **Elvis Sun's own anecdotes, NOT in the repo README.**
  Cite as anecdotes only.

## Our live reward-hacks this fences (from the research doc)
`compound_judge` empty-steps → passed=True · low-confidence-FAIL-as-PASS `orchestrator.py:781` ·
`injection_clean_boundary` 100% false-PASS · RapidMeta at-scale `cE>cN`.

## Ties to
[[src-made-benchmark]] · [[src-trinity]] · [[swipe-file]] (loss template).
