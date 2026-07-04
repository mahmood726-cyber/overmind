# Loop Engineering — Boris Cherny ("build loops, not prompts")

**Source:** the "Loop Engineering" pattern popularized by **Boris Cherny** (creator of Claude Code,
Anthropic) — *"I don't prompt Claude anymore. I write loops, and the loops do the work. My job is to
write loops."* Relayed/framed by practitioner write-ups (Cortex / @0xCortexl; Addy Osmani) and the
open-source `loop-engineering` skills.
**Verified summary:** https://noqta.tn/en/news/anthropic-loop-engineering-boris-cherny-autonomous-claude-code-2026
**Field guide:** https://lushbinary.com/blog/loop-engineering-ai-coding-agents-guide/
**Tooling:** https://github.com/cobusgreyling/loop-engineering (`loop-audit`/`loop-cost`) ·
https://github.com/selmakcby/loop-engineering ("un-foolable verification gate" skill).
**Why it matters / how it maps to us:** it is the *anatomy* our stack already partially implements — and
naming its three load-bearing parts is what exposes our single biggest gap (consensus without an objective
floor). This is the direct parent of the [[Cross-Vendor-Witness-SOP]] and the whole [[_index|plan]].

## The three load-bearing requirements
1. **VERIFY = objective gate** (test/build/lint pass — *not* "a second agent agreeing").
2. **STATE file outside the conversation** (progress persists across turns).
3. **STOP condition** (success + a hard limit).
Plus building blocks: automation/heartbeat, skills, **maker/checker** (writer ≠ stronger adversarial
reviewer), connectors that act, **cost-per-accepted-change**, a shared signal store.

## Our honest scorecard (from the research doc §1.5)
- **MEETS:** external STATE file, heartbeat/automation, Skills.
- **PARTIAL — biggest gap:** the objective-gate floor. Headline verdicts often lean on LLM judges /
  consensus-or-flag — exactly the "two optimists agreeing" the pattern warns against (`enable_llm_judge=
  False`, low-confidence FAIL silently accepted at `orchestrator.py:781`).
- **MISSING:** cost-per-accepted-change tracking.
- **Failure modes we've hit:** premature completion ("Ralph Wiggum"), goal drift, comprehension debt
  (the RapidMeta `P0-denominator-logic` at-scale bug = un-reviewed generated output), token-cost compounding.

## ⚠ Truth-first on the numbers
Cherny's quantified claims — **"~70% more shipped per head"**, **"2–3× quality boost from verification"** —
are **interview-attributed with no primary measurement or benchmark cited.** **No "8×" figure is supported
by any source** — do not repeat it. The **"loop is net-negative below ~50% acceptance"** rule and
**cost-per-accepted-change** metric are sensible practitioner heuristics, **not** measured constants.

## Build-order discipline (adopt explicitly)
**manual-reliable → Skill → loop(gate+stop) → then schedule.** A direct governance check on scheduling the
still-unmerged cluster branch before it is merged / CI-proven.

## Ties to
[[src-ai-edge-loop-guide]] (the `/loop`+`/goal` realization) · [[src-loop-library]] (concrete templates) ·
[[src-lfd]] (loss design under the loop) · [[Gated-Additive-Deploy-SOP]].
