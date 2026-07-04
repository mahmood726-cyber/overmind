# Evolve the Harness (Joel Niklaus) — CENTERPIECE

**URL:** https://huggingface.co/spaces/joelniklaus/harness-optimization (app:
https://joelniklaus-harness-optimization.hf.space/ )
**What:** automated loop that mutates the *harness* around a FIXED model, keeping changes that improve a
benchmark score. The framing of the whole [[_index|plan]].

## VERIFIED (fetched app)
- DeepSeek-V4-Pro **0% → 5.0% all-pass / 80.1% criterion** on Harvey's Legal Agent Benchmark (LAB),
  "zero model weights changed." "Mismanaged geniuses hypothesis."
- Loop = **Proposer** (Claude Opus 4.8, "adds exactly one mechanism") + **Evaluator** (24-task dev × 3
  trials; promote only if ≥1 pt on a blended score).
- Promotion rule: `score = pooled_criterion_rate + 0.5*all_pass_rate − 0.005*tokens_per_million`.
- Safeguards: one mechanism/iteration; **"never read the test split"**; deterministic validation (causal
  replay OR A/B ≥5 fix + ≥5 regression tasks).
- **"5 of top 6 harnesses are deterministic code, not prompt edits."** Robustness fixes transfer; prompt
  playbooks backfire across model families. ~$120–160 per 100-task run.

## REPORTED / UNVERIFIED
- Related **Meta-Harness** (https://yoonholee.com/meta-harness/ , stanford-iris-lab/meta-harness) — not
  fetched.
- "Sonnet-4.6 performance at 7× cost" — search-summary claim, **omitted as unverified.**

## Ties to
[[src-lfd]] (loss design) · [[src-made-benchmark]] (the Evaluator) · [[src-trinity]] (validation) ·
[[src-claude-code-docs]] (primitives the harness is built from).
