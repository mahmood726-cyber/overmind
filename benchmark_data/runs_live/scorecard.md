# Benchmark scorecard

Slice: F:\overmind\benchmark_data  
Held-out tasks: 40  
Generated: (stamp on write)

| arm | status | caught-defect | false-alarm | parity | agreement | accepted | cost/accepted | blended |
|---|---|---|---|---|---|---|---|---|
| objective-ref (witness-only floor) | RUN | 0.4286 | 0.0000 | 1.0000 | 0.2000 | 25 | 0.0000 | 0.9286 |
| C-shadow (stub reviewers) | SHADOW | 1.0000 | 0.0000 | 1.0000 | 1.0000 | 5 | 0.0000 | 1.5000 |
| objective-ref [FROZEN slice, sealed] | FROZEN | 0.2917 | 0.0000 | 1.0000 | 0.0192 | 52 | 0.0000 | 0.7917 |
| A | RUN | 0.6286 | 0.4000 | 1.0000 | 0.1875 | 16 | 0.0000 | 0.7286 |
| B | INVALID (vendor degraded, usable-rate 5%) | 0.0286 | 0.0000 | 0.0000 | 0.1282 | 39 | 0.0000 | 0.0286 |
| C | INVALID (vendor degraded, usable-rate 22%) | 0.6571 | 0.2000 | 1.0000 | 0.2500 | 16 | 0.0000 | 0.9571 |

## Win condition
_Pending: needs Arms A, B, C all run (model capacity)._

## Notes
- Split (deterministic sha256): dev=118 held_out=139 FROZEN=73 (of 330 total).
- Held-out slice scored this run: 40 tasks (defects=35, clean=5).
- AN-2 FROZEN slice is SEALED: harness-evolution never reads/scores/tunes on it; a candidate is promoted only if it also wins there (arXiv:2605.30621). It is scored below for reference only.
- Answer keys read only by the scorer. Weights pinned; scoring can report NOT_PROVEN.
- Objective reference = Arm C floor with NO reviewers: catches witness-detectable defects (impossible_cell, reproduction, ci_invalid) but structurally misses the 20 reviewer-only defects in the held-out slice (6 classes) — that gap is what the cross-vendor panel must close.
- preflight claude:oauth = DOWN (no auth (set CLAUDE_CODE_OAUTH_TOKEN via `claude setup-token`))
- preflight codex:mahmood = LIVE (ok)
- preflight codex:noreen = DOWN (JUDGE_ERROR: exit 1: 2026-07-05T22:20:12.031171Z ERROR codex_models_ma)
- preflight agy:default = LIVE (ok)
- preflight gemini:api = DOWN (JUDGE_ERROR: HTTPError: HTTP Error 429: Too Many Requests)
- Live vendors this run: ['agy', 'codex'].
- Arm B INVALID: reviewer usable-rate 5% < 50% — the vendor returned empty/envelope responses on most tasks; the verdicts are backend artifacts, not the model's judgment. NOT scored as real.
- Arm C INVALID: reviewer usable-rate 22% < 50% — the vendor returned empty/envelope responses on most tasks; the verdicts are backend artifacts, not the model's judgment. NOT scored as real.
- Arm C reviewers: ['codex', 'agy'] (distinct families).
