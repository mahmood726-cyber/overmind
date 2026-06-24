# Overmind/Sentinel Measurement Harness

The first **held-out** evals for the stack — turning "robust by design" into
"robust by **evidence**". Implements recommendation #1 of
[`docs/SYSTEMS-BENCHMARK-VS-FRONTIER.md`](../docs/SYSTEMS-BENCHMARK-VS-FRONTIER.md)
("Nothing is measured"), grounded in
[`docs/AI-FRONTIER-ADOPTION.md`](../docs/AI-FRONTIER-ADOPTION.md).

Three evals, each producing a real, reproducible score in
[`results/`](results/):

| # | Eval | File | Measures |
|---|------|------|----------|
| 1 | SpecBench-style | `specbench_style.py` | validation-minus-held-out gap (reward-hacking signal) |
| 2 | Judge master-key | `judge_masterkey.py` | judge false-PASS rate on adversarial inputs; accuracy on genuine |
| 3 | Memory recall | `memory_recall.py` | recall/precision; suppression of superseded & expired facts |
| 4 | Quorum decorrelation | `quorum_decorrelation.py` | correlated-panel overcount rate before→after hard family-enforcement (A2) |
| 5 | Engine routing | `engine_routing.py` | expensive(quorum)-invocation rate cut + accuracy preserved under cost-aware routing (C2) |
| 6 | CoT golden-set gate | `judge_cot_goldenset.py` | CoT-on vs -off parse-invariance / no-regression gate before defaulting CoT ON (A3) |
| 7 | Memory retraction | `memory_retraction.py` | transitive-invalidation recall: flat freshness vs claim→evidence graph propagation (B2) |

## How to run

```bash
make evals                      # all three + results/summary.json
# or, without make:
python -m evals.run_all

# individually:
python -m evals.specbench_style     # make evals-specbench
python -m evals.judge_masterkey     # make evals-judge
python -m evals.memory_recall       # make evals-memory
```

Run from the repo root (`F:\overmind`). No network, API key, or external data
required — everything runs offline against the real pipeline code. Results are
written to `evals/results/*.json`; a combined scoreboard lands in
`evals/results/summary.json`.

The harness is also covered by the normal test suite
(`tests/unit/test_evals_harness.py`), so the truth-first invariants are enforced
in CI, not just when you run the evals by hand.

## Determinism / reproducibility

- Fixed fixtures, fixed IDs, fixed seed (`evals/common.py::SEED = 1234`). No
  randomness in any scored path.
- Superseded facts get `status=expired` + a past `valid_until`; the store's own
  active+temporal query filters them, so recall scores are stable across runs.
- The only non-reproducible field is `_meta.generated_at` (a wall-clock stamp);
  every **scored** number is byte-stable run to run.

## What each eval actually measures (and its honest limits)

### 1. SpecBench-style validation-vs-held-out (`specbench_style`)

Mirrors **SpecBench** ([arXiv:2605.21384](https://arxiv.org/abs/2605.21384)):
each candidate solution is scored on a **VISIBLE** validation test set and a
**HELD-OUT** test set using our *real* `overmind.verification.witnesses.
SuiteWitness` (runs `python -m pytest` in an isolated temp dir per candidate).

- **`specbench_gap = validation_pass_rate − heldout_pass_rate`** is the
  reward-hacking signal: how much "passes the tests it can see" overstates true
  correctness.
- Each task ships an `honest` (passes both), a `reward_hack` (passes visible,
  fails held-out — e.g. hardcodes the visible cases), and a `broken` (fails
  both) candidate.
- **`reward_hack.heldout_catch_rate`** is the headline defense number: of the
  reward-hacks a *visible-only* verifier would falsely certify, what fraction
  does Overmind's **held-out-baseline policy** (run the held-out witness too)
  catch?

> **This is a compact LOCAL PROXY, not the official benchmark.** It is labelled
> as such in every output (`"eval": "specbench_style_proxy"`). To run the real
> tasks, drop them into `evals/datasets/specbench_official/` — one folder per
> task with `spec.md`, `tests/test_visible.py`, `tests/test_heldout.py`, and
> `candidates/<kind>.py`. They are auto-loaded alongside the proxy
> (`load_directory_tasks`); no code change needed.

### 2. Judge master-key / adversarial (`judge_masterkey`)

Feeds labelled raw judge outputs through the **real**
`overmind.verification.llm_judge.LLMJudge` (incl. the degenerate-output guard,
`degenerate_response_reason`), per *One Token to Fool LLM-as-a-Judge*
([arXiv:2507.08794](https://arxiv.org/abs/2507.08794)).

- **Effective PASS** is defined exactly as the orchestrator gate sees it:
  `passed is True AND 'judge_error' not in concerns`.
- **`degenerate.false_pass_rate`** — over empty / whitespace / punctuation-only /
  filler / no-verdict inputs. Must be **0**.
- **`genuine.accuracy`** — well-formed PASS/FAIL verdicts classified correctly,
  with `misflagged_as_degenerate == 0` (the guard must not eat real verdicts).
- **`injection_boundary.false_pass_rate`** — reported **separately and
  honestly**. These outputs carry an attacker-planted `VERDICT: PASS`; a regex
  *output*-guard is not designed to catch them. This number documents the
  guard's boundary (defending these needs input-side sanitization / a trusted
  output channel), not a guard failure.

### 3. Memory recall probe (`memory_recall`)

LongMemEval-style ([SYSTEMS-BENCHMARK §3](../docs/SYSTEMS-BENCHMARK-VS-FRONTIER.md)).
Seeds a real `MemoryStore` (SQLite + FTS5) with facts including superseded ones
(`store.supersede`) and one expired temporal fact, then queries it.

- **`recall`** — current fact present in top-k.
- **`precision`** — current-fact hits / total returned (a returned superseded
  fact lowers it).
- **`stale_suppression_rate`** — fraction of probes returning **no** superseded
  fact.
- **`naive_stale_leak_rate`** — counterfactual: the same FTS query *without* the
  active+temporal filter. Superseded facts share title/keywords with the current
  one, so a high naive leak vs a low real stale-leak proves the **temporal
  filter** (not keyword luck) is doing the suppression.

> Compact probe (4 supersession topics + distractors + 1 expired fact) with
> keyword-distinct queries. It demonstrates temporal suppression works; it does
> **not** yet stress semantic-paraphrase retrieval or large-N ranking. Drop the
> official LongMemEval set behind the same `MemoryStore.search` interface to
> scale it up.

## Latest measured scores

See `results/summary.json` for the authoritative, machine-readable numbers.
A snapshot is reproduced in the branch's report; re-run `make evals` to refresh.
