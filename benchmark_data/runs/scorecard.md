# Benchmark scorecard

Slice: F:\overmind\benchmark_data  
Held-out tasks: 139  
Generated: (stamp on write)

| arm | status | caught-defect | false-alarm | parity | agreement | accepted | cost/accepted | blended |
|---|---|---|---|---|---|---|---|---|
| objective-ref (witness-only floor) | RUN | 0.3413 | 0.0000 | 1.0000 | 0.1354 | 96 | 0.0000 | 0.8413 |
| C-shadow (stub reviewers) | SHADOW | 1.0000 | 0.0000 | 1.0000 | 1.0000 | 13 | 0.0000 | 1.5000 |
| objective-ref [FROZEN slice, sealed] | FROZEN | 0.2917 | 0.0000 | 1.0000 | 0.0192 | 52 | 0.0000 | 0.7917 |
| A | STAGED (needs a live frontier model) | n/a | n/a | n/a | n/a | - | n/a | n/a |
| B | STAGED (needs a live frontier model x3) | n/a | n/a | n/a | n/a | - | n/a | n/a |
| C | STAGED (needs >=2 distinct live families; have []) | n/a | n/a | n/a | n/a | - | n/a | n/a |

## Win condition
_Pending: needs Arms A, B, C all run (model capacity)._

## Notes
- Split (deterministic sha256): dev=118 held_out=139 FROZEN=73 (of 330 total).
- Held-out slice scored this run: 139 tasks (defects=126, clean=13).
- AN-2 FROZEN slice is SEALED: harness-evolution never reads/scores/tunes on it; a candidate is promoted only if it also wins there (arXiv:2605.30621). It is scored below for reference only.
- Answer keys read only by the scorer. Weights pinned; scoring can report NOT_PROVEN.
- Objective reference = Arm C floor with NO reviewers: catches witness-detectable defects (impossible_cell, reproduction, ci_invalid) but structurally misses the 83 reviewer-only defects in the held-out slice (6 classes) — that gap is what the cross-vendor panel must close.
- preflight claude:oauth = DOWN (no auth (set CLAUDE_CODE_OAUTH_TOKEN via `claude setup-token`))
- preflight codex:mahmood = DOWN (JUDGE_ERROR: exit 1: OpenAI Codex v0.142.3
--------
workdir: F:\overmi)
- preflight codex:noreen = DOWN (JUDGE_ERROR: exit 1: OpenAI Codex v0.142.3
--------
workdir: F:\overmi)
- preflight agy:default = DOWN (JUDGE_ERROR: agy returned empty text)
- preflight gemini:api = DOWN (JUDGE_ERROR: HTTPError: HTTP Error 429: Too Many Requests)
- Live vendors this run: NONE.
