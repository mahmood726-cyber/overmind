# Benchmark scorecard

Slice: F:\overmind\benchmark_data  
Held-out tasks: 139  
Generated: (stamp on write)

| arm | status | caught-defect | false-alarm | parity | agreement | accepted | cost/accepted | blended |
|---|---|---|---|---|---|---|---|---|
| objective-ref (witness-only floor) | RUN | 0.3413 | 0.0000 | 1.0000 | 0.1354 | 96 | 0.0000 | 0.8413 |
| C-shadow (stub reviewers) | SHADOW | 1.0000 | 0.0000 | 1.0000 | 1.0000 | 13 | 0.0000 | 1.5000 |
| objective-ref [FROZEN slice, sealed] | FROZEN | 0.2917 | 0.0000 | 1.0000 | 0.0192 | 52 | 0.0000 | 0.7917 |
| A | RUN | 0.8016 | 0.3077 | 1.0000 | 0.2647 | 34 | 0.0000 | 0.9939 |
| B | RUN | 0.7698 | 0.2308 | 1.0000 | 0.2564 | 39 | 0.0000 | 1.0390 |
| C | RUN | 0.9206 | 0.4615 | 1.0000 | 0.4118 | 17 | 0.0000 | 0.9591 |

## Win condition
**Verdict: NOT_PROVEN** (C>A=False, C>B=True, affordable=True)
- C did NOT beat A on caught-defect + agreement with FAR no worse.

## Notes
- Split (deterministic sha256): dev=118 held_out=139 FROZEN=73 (of 330 total).
- Held-out slice scored this run: 139 tasks (defects=126, clean=13).
- AN-2 FROZEN slice is SEALED: harness-evolution never reads/scores/tunes on it; a candidate is promoted only if it also wins there (arXiv:2605.30621). It is scored below for reference only.
- Answer keys read only by the scorer. Weights pinned; scoring can report NOT_PROVEN.
- Objective reference = Arm C floor with NO reviewers: catches witness-detectable defects (impossible_cell, reproduction, ci_invalid) but structurally misses the 83 reviewer-only defects in the held-out slice (6 classes) — that gap is what the cross-vendor panel must close.
- preflight claude:oauth = LIVE (ok)
- preflight codex:mahmood = DOWN (unavailable (no codex CLI / CODEX_HOME))
- preflight codex:noreen = DOWN (unavailable (no codex CLI / CODEX_HOME))
- preflight agy:default = LIVE (ok)
- preflight gemini:api = DOWN (JUDGE_ERROR: HTTPError: HTTP Error 429: Too Many Requests)
- Live vendors this run: ['agy', 'claude'].
- Arm C reviewers: ['claude', 'agy'] (distinct families).
