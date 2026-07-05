# reference-library — every cited URL

Curated link library (vault workflow #3). Grouped by role.

## Framing / practitioner
- **AI Agents That Matter** (Kapoor, Stroebl, Siegel, Nadgir, Narayanan, 2024): https://arxiv.org/abs/2407.01502 — **FOUNDATIONAL benchmark-design reference** (jointly optimize cost+accuracy; adequate holdout at the right generality level or agents overfit; model- vs downstream-developer needs; standardization/error-bars). Cited in `harness/BENCHMARK.md` / `BENCHMARK_RESULTS.md` / `WORLD_CLASS_SPEC §3`. Cross-check 2026-07-05: aligned 4/6, adopted 2 deltas (Wilson CIs; fixture-leakage disclosure).
- **RAG-tuning loop (h100envy)** — *external CORROBORATION, nothing to adopt*: independently arrives at train/held-out split + noise-threshold + budget/run brakes + log + objective-check — all of which we already have; our **frozen slice (AN-2) + Kish n_eff (AN-3)** go further. Confirmatory, not new.
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
- AutoMem (Stanford — learnable memory, HIGH): https://arxiv.org/pdf/2607.01224 — [[src-automem]]
- Right in the Right Way (MIT — RLVR + human demos, anti-reward-hacking): https://arxiv.org/abs/2607.01181 — [[src-right-in-the-right-way]]
- Related (not fetched): Meta-Harness https://yoonholee.com/meta-harness/

## Background papers (pure-ML-theory — NOT actionable)
- Attention Residuals (Kimi Team, **excluded** — pretraining technique): https://arxiv.org/abs/2603.15031 — [[src-attention-residuals-excluded]]
- A Hippocampus for Linear Attention / HOLA (Wanyun Cui — memory metaphor only): https://arxiv.org/abs/2607.02303 — [[src-hippocampus-linear-attention]]
- A Mathematical Introduction to Diffusion Models (Jianfeng Lu — reference-only): https://arxiv.org/abs/2607.01693 — [[src-diffusion-models-intro]]

## Candidate tools / repos (audit before adopting)
- Ragas (RAG eval, Apache-2.0, ~14.6k★): https://github.com/explodinggradients/ragas — [[tool-ragas]]
- Weekend repos (10, resolved + triaged): [[candidate-tools-weekend-repos]]
  - ComposioHQ/agent-orchestrator (HIGH): https://github.com/ComposioHQ/agent-orchestrator
  - Yeachan-Heo/oh-my-claudecode (HIGH): https://github.com/Yeachan-Heo/oh-my-claudecode
  - NousResearch/hermes-agent (MED-HIGH): https://github.com/NousResearch/hermes-agent
  - Gitlawb/openclaude (MED-HIGH): https://github.com/Gitlawb/openclaude
  - paperclipai/paperclip (MED): https://github.com/paperclipai/paperclip
  - open-gitagent/clawless (LOW-MED): https://github.com/open-gitagent/clawless
  - google-research/timesfm (LOW): https://github.com/google-research/timesfm
  - larksuite/cli (LOW): https://github.com/larksuite/cli
  - 666ghj/MiroFish (LOW): https://github.com/666ghj/MiroFish
  - 🚫 elder-plinius/ST3GG (AVOID — jailbreak/adversarial): https://github.com/elder-plinius/ST3GG

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
- Weekend-repo **star counts** — as reported 2026-07-04; Hermes "209k" and Paperclip "71k" are **implausibly
  high** → treat as unverified / possible star inflation.
- AutoMem / Hippocampus / Right-in-the-Right-Way / Diffusion — arXiv summaries recorded **per Mahmood's
  brief** (framing accepted, not independently re-derived from the PDFs this pass).
