# Benchmark scorecard

Slice: F:\overmind\benchmark_data  
Held-out tasks: 40  
Generated: (stamp on write)

| arm | status | caught-defect | false-alarm | parity | agreement | accepted | cost/accepted | blended |
|---|---|---|---|---|---|---|---|---|
| objective-ref (witness-only floor) | RUN | 0.4286 | 0.0000 | 1.0000 | 0.2000 | 25 | 0.0000 | 0.9286 |
| C-shadow (stub reviewers) | SHADOW | 1.0000 | 0.0000 | 1.0000 | 1.0000 | 5 | 0.0000 | 1.5000 |
| objective-ref [FROZEN slice, sealed] | FROZEN | 0.2917 | 0.0000 | 1.0000 | 0.0192 | 52 | 0.0000 | 0.7917 |
| A | RUN | 0.6000 | 0.4000 | 1.0000 | 0.1765 | 17 | 0.0000 | 0.7000 |
| B | RUN | 0.6286 | 0.4000 | 1.0000 | 0.1875 | 16 | 0.0000 | 0.7286 |
| C | RUN | 0.8286 | 0.4000 | 1.0000 | 0.3333 | 9 | 0.0000 | 0.9286 |

## Win condition
**Verdict: WORLD_CLASS** (C>A=True, C>B=True, affordable=True)

## Notes
- Split (deterministic sha256): dev=118 held_out=139 FROZEN=73 (of 330 total).
- Held-out slice scored this run: 40 tasks (defects=35, clean=5).
- AN-2 FROZEN slice is SEALED: harness-evolution never reads/scores/tunes on it; a candidate is promoted only if it also wins there (arXiv:2605.30621). It is scored below for reference only.
- Answer keys read only by the scorer. Weights pinned; scoring can report NOT_PROVEN.
- Objective reference = Arm C floor with NO reviewers: catches witness-detectable defects (impossible_cell, reproduction, ci_invalid) but structurally misses the 20 reviewer-only defects in the held-out slice (6 classes) — that gap is what the cross-vendor panel must close.
- preflight claude:oauth = LIVE (ok)
- preflight codex:mahmood = DOWN (JUDGE_ERROR: exit 1: OpenAI Codex v0.142.3
--------
workdir: F:\overmi)
- preflight codex:noreen = DOWN (JUDGE_ERROR: exit 1: 2026-07-06T11:28:37.480455Z ERROR codex_models_ma)
- preflight agy:default = LIVE (ok)
- preflight gemini:api = DOWN (JUDGE_ERROR: HTTPError: HTTP Error 429: Too Many Requests)
- Live vendors this run: ['agy', 'claude'].
- Arm C reviewers: ['claude', 'agy'] (distinct families).
