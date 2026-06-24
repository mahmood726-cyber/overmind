# AI-Frontier Quick Wins — Implementation Notes

**Date:** 2026-06-24
**Branch:** `ai-frontier-quickwins-2026-06-24`
**Source plan:** [AI-FRONTIER-ADOPTION.md](AI-FRONTIER-ADOPTION.md) §2 "Quick wins"
**Status:** implemented, tested, **not merged** — left for review.

Implements the 5 §2 quick-win items. Truth-first throughout: every judge change
only ever makes a verdict *stricter* or *abstain*; none makes PASS easier on
missing/degenerate evidence. No force-push; no secret-key handling touched.

---

## Item 1 (A1) — Judge degenerate / "master-key" output guard  ★ highest value

**Threat:** *One Token to Fool LLM-as-a-Judge* (arXiv:2507.08794) — empty,
whitespace, punctuation-only (`:`), or generic-filler ("Let's solve this step by
step.") judge outputs can force a false-positive PASS. This is the same family as
our `SKIP-as-pass` and `placeholder-leak` lessons, generalized to the LLM judge.

**Where the lesson lived:** `overmind/verification/llm_judge.py::_parse_verdict`
already required an explicit `VERDICT: PASS` line and tagged `judge_error` /
`judge_parse_error` for unparseable replies (orchestrator.py gates on
`judge_error` → falls back to tests-only). Extended that with an explicit,
named, logged degenerate guard.

**Changes:**
- `overmind/verification/llm_judge.py`: new `degenerate_response_reason()` helper
  (detects empty/whitespace, punctuation/markup-only, filler-without-verdict).
  `_parse_verdict` calls it right after the `JUDGE_ERROR` check and returns
  `passed=False, confidence=0.0, concerns=["judge_error","judge_degenerate"]`
  + a WARNING log. `passed=False` is defensive truth-first (never present a
  degenerate as passed even though the orchestrator already gates on
  `judge_error`); `judge_error` preserves the established escalate/fail-safe
  (tests-only) path. Deliberately conservative: any reply containing a real
  PASS/FAIL/VERDICT token is left to the parser, and an ordinary unparseable
  reply ("I don't understand the format") keeps its `judge_parse_error` tag.
- `overmind/diagnosis/llm_judge.py`: reuses the same helper to reject degenerate
  replies before JSON parse → returns `None` (keeps the original UNKNOWN
  diagnosis; never fabricates an upgrade). This judge cannot emit a ship PASS, so
  it's defense-in-depth.

**Tests:** `tests/unit/test_llm_judge.py` — one case per degenerate type (empty,
whitespace, punctuation, filler) asserting NOT-PASS + `judge_degenerate`, plus a
regression that a real PASS opening with filler still parses.

## Item 2 (A5) — Temporal validity frontmatter on markdown memory

Brings the markdown layer to parity with the SQLite `MemoryStore`
(`valid_from`/`valid_until`/supersede already there).

**Changes — `overmind/memory/file_index.py`:**
- `_parse_date`, `_not_yet_valid`, `_is_superseded`, `is_current`,
  `historical_reason`. `is_current` = not expired (`valid_until` past) AND not
  future-dated (`valid_from` ahead) AND not `superseded_by` another fact.
- `cmd_recall` now splits results into current `results` and a `historical`
  list (each with a reason) — superseded/expired/future facts never surface as
  current, but stay retrievable as history.
- `consolidate_report` gains a `non_current` section (the A5 "lint").

**Back-compat:** fieldless files → `is_current({}) is True` (always current).
Malformed dates are ignored, not fatal. `bm25_recall` signature unchanged (the
self-recall eval in `ecosystem_eval.py` is unaffected).

**Tests:** `tests/unit/test_file_index_consolidate.py` — superseded fact not
current, `valid_from` in future excluded, `valid_from` in past current, fieldless
back-compat, and an `is_current` matrix.

## Item 3 (A3) — CoT + rubric judge prompt (config-controlled, no swapping)

Per arXiv:2604.23178: CoT universally helps; style bias dominates; **position
bias negligible → no answer/position swapping** (explicitly skipped per the plan).

**Changes:**
- `overmind/verification/llm_judge.py`: `JUDGE_PROMPT_TEMPLATE_COT` (step-by-step
  reasoning + fixed RELEVANCE/ACCURACY/EVIDENCE/LOGIC rubric + truth-first
  "missing/skipped evidence ⇒ not PASS" rule), with a byte-identical trailing
  output block so `_parse_verdict` and the degenerate guard apply unchanged.
  `_cot_enabled()` reads `OVERMIND_JUDGE_COT`. `LLMJudge(use_cot=...)`.
- `overmind/verification/judge_factory.py`: `build_judge(use_cot=...)` threads
  the flag to every LLMJudge (fallback and quorum).

**Default OFF** (opt-in via `OVERMIND_JUDGE_COT=1` or `build_judge(use_cot=True)`)
— zero change to current judge behavior unless enabled, satisfying the
no-regression constraint. Recommended ON after a live golden-set check.

**Tests:** `tests/unit/test_judge_factory.py` — default off, enable via param/env,
prompt contains rubric + reasoning + intact output contract, quorum propagation.

## Item 4 (A2 partial) — Quorum decorrelation: effective-vote estimate

Per arXiv:2605.29800 ("Nine Judges, Two Effective Votes"): same-family judges
share correlated errors, so nominal panel size overstates independence.

**Changes — `overmind/verification/judge_factory.py`:**
- `ENGINE_FAMILY` map (claude→anthropic, codex/codex-noreen→openai,
  agy/gemini→google, local, stub), `family_for_engine`,
  `estimate_effective_votes()` → `EffectiveVotes(nominal, distinct_families,
  families, effective_votes, warning)`. Heuristic: each extra same-family judge
  adds only `0.25` of an independent vote.
- `build_judge` quorum path logs a WARNING when a panel over-counts independence
  (e.g. `claude,codex,codex-noreen` → 3 nominal / 2 families / ~2.25 effective)
  and an INFO line with the estimate.
- `QuorumJudge`/`QuorumVerdict` carry `nominal_votes`/`effective_votes`/
  `distinct_families`; the verdict adds a `quorum_correlated_panel` concern and
  the effective-vote count in its reasoning → visible in the bundle.

**Minimal scope (as requested):** detect + log + surface; does NOT hard-enforce
different families (no behavior break; quorum stays opt-in). Hard enforcement is
deferred (see below).

**Tests:** `tests/unit/test_judge_factory.py` — same-family flags low effective
votes, all-same warns hardest, all-different no warning, agy≡gemini family, and
the verdict carries the estimate + concern + build-time warning.

## Item 5 (C3) — Scheduled memory consolidation

**Changes:**
- `scripts/consolidate_memory.bat`: runs `overmind.cli notes consolidate --apply`
  (deterministic: archives expired/`>365d`-stale facts — reversible move to
  `<memory>/archive/`, never deletes/edits — and logs the dedup/orphan/
  non-current report). Same `OVERMIND_PYTHON` Task-Scheduler-PATH workaround as
  `nightly_verify.bat`.
- `scripts/install_overmind_task.ps1`: registers a third task **"Overmind Memory
  Consolidation"** — weekly Sunday 04:00 (after the 03:00 nightly verifier),
  `MultipleInstances IgnoreNew`, 30-min limit. PS1 parses clean.

The reflective LLM `consolidate-memory` skill (merge/rewrite/re-link) stays a
**manual, interactive** pass — only the deterministic decay pass is automated.

---

## Intentionally deferred

- **A2 hard-enforcement** of different-family quorum panels (currently warn-only,
  per "minimal version" in the task). Would reject/auto-substitute same-family
  panels at construction.
- **A3 default-on** + a live judge golden-set re-run to validate the CoT prompt
  empirically before flipping the default.
- Wiring `OVERMIND_JUDGE_COT` into `policies.yaml` limits (currently env-only,
  matching how `enable_llm_judge` is also env-overridable).
- The diagnosis-judge degenerate guard is intentionally light (that judge can't
  emit a ship PASS).
