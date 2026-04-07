# OVERMIND v1

OVERMIND is a local orchestration system for supervising terminal coding agents with an evidence-first workflow. This repository implements the first milestone from the architecture spec:

- one-project indexing
- up to three concurrent runner sessions
- SQLite-backed state
- terminal transcript capture
- loop and proof-gap detection
- verification before completion
- checkpoint and insight logging

## Scope

This build is intentionally conservative. It favors observable behavior over deep automation:

- the top-level supervisor works from terminal output, command results, manifests, guidance files, and stored summaries
- the indexer reads manifests and guidance files, not arbitrary source trees
- runners are registered from YAML and marked offline if their commands are not available
- verification runs from discovered project commands and task requirements

## Layout

- `config/`: roots, runners, policies, ignores, verification profiles
- `overmind/`: application package
- `data/`: sqlite state, transcripts, checkpoints, artifacts, logs, cache
- `tests/`: unit and integration tests

## Quick Start

```powershell
cd C:\overmind
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
overmind scan
overmind run-once
```

## Useful Commands

```powershell
overmind scan
overmind portfolio-audit
overmind show-state
overmind enqueue-demo --project-id <project_id>
overmind run-once
overmind run-loop --iterations 10 --sleep-seconds 5
```

## Notes

- Default runner commands in `config/runners.yaml` are samples and may need adjustment for the local machine.
- `run-once` performs a single orchestration tick. `run-loop` is the long-running mode.
- `portfolio-audit` writes a machine-specific project and workflow report under `data/artifacts/`.
- Checkpoints are written under `data/checkpoints/`.
