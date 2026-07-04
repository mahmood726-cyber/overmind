# AI Edge (@aiedge_) — beginner's Loop Engineering guide

**What:** the concrete `/loop`+`/goal` template + 6-part loop anatomy. References Boris Cherny's loop
pattern and Fable 5. **Practitioner guide** — command claims VERIFIED against the Claude Code docs.

## VERIFIED (commands confirmed real — [[src-claude-code-docs]])
`/loop [interval] [prompt]` · `/goal [condition]` · `/schedule` · `/compact` · `/effort [low|…|xhigh|max]`.

## 6-part loop anatomy → our building blocks
1. TRIGGER (`/schedule`, `/loop`) 2. EXECUTION (doer) 3. VERIFIER (`/goal` grades; tests/build/screenshot)
4. STOP RULES (success + failure + token/$ budget, explicit) 5. MEMORY (progress.md) 6. SKILLS (keep SHORT).

## Goal-condition mindset
A prompt says WHAT; a `/loop`+`/goal` says WHEN to STOP (a verifiable end state).
Template: `/loop [end state], only touching [scope], stop after [X iters or $budget], use [skill], use
verifier agents for [checkpoint], keep a memory file at [path].`

## Pro-tips (baked into [[swipe-file]])
Cap BOTH iterations AND $ · default effort `high`, `xhigh` only for complex checkpoints · subagents get
fresh context (why the checker decorrelates) · `/compact` before long runs.

## REPORTED / UNVERIFIED
"/goal runs a separate fast grader model each turn" — guide's framing; docs confirm work-until-condition,
not the separate-grader mechanism.

## Ties to
[[swipe-file]] (the 4 filled-in specs) · [[src-loop-library]].
