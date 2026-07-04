# reference-library — every cited URL

Curated link library (vault workflow #3). Grouped by role.

## Framing / practitioner
- Evolve the Harness (Niklaus): https://huggingface.co/spaces/joelniklaus/harness-optimization — [[src-evolve-the-harness]]
- Loss-Function Development (Elvis Sun): https://github.com/elvisun/loss-function-development — [[src-lfd]]
- Loop Library (Forward Future): https://signals.forwardfuture.com/loop-library/ — [[src-loop-library]]
- AI Edge Loop Engineering guide (@aiedge_) + Fable-5 — [[src-ai-edge-loop-guide]]
- Loop Engineering / Boris Cherny (verified summary): https://noqta.tn/en/news/anthropic-loop-engineering-boris-cherny-autonomous-claude-code-2026 — [[src-loop-engineering-cherny]]
  - field guide: https://lushbinary.com/blog/loop-engineering-ai-coding-agents-guide/ · tooling: https://github.com/cobusgreyling/loop-engineering , https://github.com/selmakcby/loop-engineering

## Papers
- MADE (materials closed-loop): https://arxiv.org/abs/2601.20996 — [[src-made-benchmark]]
- TRINITY (evolved coordinator, ICLR'26): https://arxiv.org/abs/2512.04695 · https://sakana.ai/trinity/ — [[src-trinity]]
- Scheduler-graph (SGH, position paper): https://arxiv.org/abs/2604.11378 — [[src-scheduler-graph-sgh]]
- Attention Residuals (Kimi Team, **excluded** — pretraining technique): https://arxiv.org/abs/2603.15031 — [[src-attention-residuals-excluded]]
- Related (not fetched): Meta-Harness https://yoonholee.com/meta-harness/

## Tools
- Claude Code docs: https://code.claude.com/docs — [[src-claude-code-docs]]
- MemClaw (governed memory): https://github.com/caura-ai/caura-memclaw · https://memclaw.net/ — [[src-memclaw]]
- mattpocock/skills: https://github.com/mattpocock/skills — [[src-mattpocock-skills]]
- sanyuan-skills: https://github.com/sanyuan0704/sanyuan-skills — [[src-sanyuan-skills]]

## Verification source reports (on disk — `F:\ubcma\verification\`)
- `2026-07-04-agy-thirdvendor.md` — [[Triple-Vendor-Transport-NMA-Witness]], [[agy-New-Comparator-Defects]]
- `2026-07-04-codex-postreauth.md` — [[Triple-Vendor-Transport-NMA-Witness]], [[RapidMeta-Repool-Findings]]
- `2026-07-04-codex-two-seat.md` — cross-vendor fallback re-run
- `2026-07-04-p0p1-fixes.md` — [[P0-P1-Bug-Fixes]]

## Session deliverables (on disk — `F:\overmind\workflow-upgrade\`)
- `2026-07-04-cutting-edge-improvements.md` — research/design doc (§1–5, T1–T12)
- `2026-07-04-implementation-checklist.md` — full implementation checklist

## Truth-first flags (do NOT cite as fact)
- "8×" loop productivity — no source supports it.
- "~50% acceptance break-even", "~70% more per head", "2–3× verification" — interview-attributed heuristics.
- "Sonnet-4.6 at 7× cost" (Niklaus) — search-summary, unverified.
- "50× / 30h / $40", "cheated 3×" (LFD) — Elvis Sun anecdotes, not in repo.
- "Fable is world's best at long tasks" — unverified marketing.
- TRINITY "bigger manager = worse" and "verifier must differ" — NOT in the paper.
- eToro MemClaw metrics — README claim, not independently measured.
