# Pluggable LLM judge engines

Overmind's LLM judge (`overmind/verification/`) is engine-pluggable. It no
longer depends on a single `GEMINI_API_KEY`; the backend is selectable by
config/env with a sane default and graceful fallback when the primary engine is
down or over quota.

> The judge feeds orchestrator scoring / memory / dream. It is **not** the ship
> verdict — that comes from the deterministic witnesses (suite, smoke, Semgrep,
> pip-audit, numerical, determinism). Engine choice here changes robustness of
> the LLM-judged components, not the cert gate.

## Engines

| name           | backend            | transport                                   | model-selection role |
|----------------|--------------------|---------------------------------------------|----------------------|
| `claude`       | ClaudeCodeBackend  | `claude -p` (stdin)                         | hard reasoning, correctness-critical judging (default primary) |
| `codex`        | CodexBackend       | `codex exec` w/ `CODEX_HOME=~/.codex`       | parallel verification bursts (mahmood seat) |
| `codex-noreen` | CodexBackend       | `codex exec` w/ `CODEX_HOME=~/.codex-noreen`| parallel verification bursts (noreen seat) |
| `agy`          | AgyBackend         | agy-driver (Antigravity/Gemini over OAuth)  | Gemini quota off the shared API key |
| `gemini`       | GeminiBackend      | Gemini REST API (`GEMINI_API_KEY`)          | API backstop |
| `local`        | LocalModelBackend  | local Ollama-style runtime (Gemma/Qwen)     | cheap high-volume, non-correctness-critical (**off by default**) |
| `stub`         | StubBackend        | deterministic                               | tests |

## Configuration

- `OVERMIND_ENABLE_LLM_JUDGE` — `1`/`true` to enable the judge at all
  (unchanged; default off).
- `OVERMIND_JUDGE_ENGINE` — comma/semicolon-separated, ordered. Default
  `claude,gemini` (strong primary, API backstop).
- `OVERMIND_JUDGE_MODE` — `fallback` (default) or `quorum`.
  - **fallback**: try engines in order; skip any whose `available()` is false;
    a `JUDGE_ERROR:` (down / over-quota) falls through to the next. Only when
    every engine fails does the judge return `judge_error`, at which point the
    orchestrator falls back to test-suite-only verification.
  - **quorum**: build a `QuorumJudge` over all listed engines (cross-model
    ensemble; verdict passes iff a threshold of available backends agree).
- `OVERMIND_LOCAL_MODEL` — `1` to enable the `local` lane (off by default).
- `OVERMIND_CODEX_HOME_MAHMOOD` / `OVERMIND_CODEX_HOME_NOREEN` — override the
  per-seat `CODEX_HOME`.
- `AGY_DRIVER_PATH` — override the agy-driver location (default
  `~/agy-driver/agy_driver.py`).

### Examples

```bash
# Default (claude primary, gemini backstop)
OVERMIND_ENABLE_LLM_JUDGE=1 python -m overmind.cli run-once

# Cross-model ensemble for a high-stakes pass
OVERMIND_ENABLE_LLM_JUDGE=1 OVERMIND_JUDGE_ENGINE=claude,gemini,codex \
  OVERMIND_JUDGE_MODE=quorum python -m overmind.cli run-once

# Cheap local triage lane (must opt in)
OVERMIND_ENABLE_LLM_JUDGE=1 OVERMIND_LOCAL_MODEL=1 \
  OVERMIND_JUDGE_ENGINE=local,claude python -m overmind.cli run-once
```

## Security

- Subprocess backends run under a scrubbed env (`safe_subprocess_env`) plus only
  the explicit overrides they need (e.g. `CODEX_HOME`). Codex runs
  `--sandbox read-only --skip-git-repo-check` so a judge never mutates a repo.
- No secret values are logged or echoed; keys are read from env/`.env` only.
- The misconfiguration guard `check_judge_engine_config` in
  `overmind.infra_invariants` FAILs if `OVERMIND_JUDGE_ENGINE` names an unknown
  backend.
