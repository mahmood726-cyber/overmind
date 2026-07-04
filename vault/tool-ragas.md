# Tool — Ragas (RAG/LLM evaluation) — MEDIUM-HIGH relevance

**Repo (verified):** https://github.com/explodinggradients/ragas · **License:** Apache-2.0 ·
**~14.6k★** · Python (83%) · 100% open source.
**What:** an LLM/RAG **evaluation framework** — scores **faithfulness** (answer grounded in source),
**answer relevance**, **context precision / recall**; **auto-generates** test/eval datasets from your own
data; integrates with LangChain + observability tools; works via OpenAI-compatible clients; CI/CD hooks.

## Why it maps to us
1. **Our doc-extraction pipeline IS effectively RAG** (OCR → extract numbers/claims from papers). Ragas
   **faithfulness** is the truth-first check that an extracted number/claim **matches the source page** —
   use it as an **objective-ish gate** on the extraction / summarization lanes.
2. **Eval-set generation operationalizes the LFD "build the private eval set" moat** ([[src-lfd]]) — turns
   our own corpus into a scored, growing eval instead of hand-authoring cases.
3. Fits the checklist's **verifier / objective-gate** item for the **LLM-mediated lanes** (extraction,
   journal-upgrade claim-fidelity).

## ⚠ Honest caveat (record this)
Ragas scores with **LLM-as-JUDGE**, which our own workflow research flags as **softer than a hard objective
gate** ([[src-loop-engineering-cherny]] "two optimists agreeing"). So it is a **COMPLEMENT for
text-generation / extraction quality**, **NOT a replacement** for the deterministic gates on the **pooling
math** — byte/numeric diff, R-parity, `node --check` **stay the floor** ([[Gated-Additive-Deploy-SOP]]).
Treat a Ragas faithfulness score as a WARN-tier signal that a claim *may* be ungrounded, to be confirmed by
a harder check, not as a ship gate on numbers.

## Security
Standard Python package (Apache-2.0); it *calls out* to an LLM to score — so **extracted content + source
text leave to whatever model backend you configure.** Use a local/OpenAI-compatible endpoint you trust for
sensitive corpora; audit the data path before running it over unpublished trial data.

## Tier
**Actionable tool (eval / verification lane).**

## Ties to
[[src-lfd]] (private eval-set moat) · [[Gated-Additive-Deploy-SOP]] (deterministic gates stay the floor) ·
[[RapidMeta-QA-SOP]] (objective gate on LLM-mediated lanes) · [[candidate-tools-weekend-repos]] ·
[[reference-library]].
