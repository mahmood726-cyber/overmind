# AUTH PREFLIGHT RUNBOOK — Codex + agy (reliability item 3)

**Why:** `codex login status` (and any session-presence check) **lies** — a seat can report
"logged in" while its refresh token is 401-revoked, so work dispatched to it silently fails. The only
truthful check is a **real `codex exec` / `agy --print` smoke**, which is what
`overmind/reliability/auth_preflight.py` and `scripts/auth_preflight.py` run **before dispatching
vendor work**. Source of record: `vault/02-SOPs/Codex-agy-Auth-Recipe-SOP.md`.

## Run the preflight (truthful check)
```bash
python scripts/auth_preflight.py        # exit 0 if any non-Claude vendor live; prints per-seat live/degraded
```
It runs `codex exec` (effort=low) on each seat and `agy --print`, and reports each seat **live** or
**degraded** — never "logged in" without a real completion.

## Codex — two seats, per-seat CODEX_HOME (auth is per-CODEX_HOME)
| Seat | `CODEX_HOME` | Env override | Account |
|---|---|---|---|
| A / default | `~/.codex` | `OVERMIND_CODEX_HOME_MAHMOOD` | `mahmood726` (gpt-5.5) |
| B / noreen | `~/.codex-noreen` | `OVERMIND_CODEX_HOME_NOREEN` | 2nd seat |

Set `CODEX_HOME` **before** `codex login` / `codex exec` to target a seat. Store paths as `~/...`
(a hardcoded `C:\Users\...` is a Sentinel BLOCK).

## Recovery recipe when a seat is 401 / "refresh token revoked"
Re-auth is **interactive-only** (headless subprocess cannot re-mint the token). On **pc1**:
```bash
# target the degraded seat (example: noreen)
export CODEX_HOME=~/.codex-noreen      # PowerShell: $env:CODEX_HOME="$HOME\.codex-noreen"
codex logout
codex login                            # completes browser OAuth; restores the seat
codex exec -c model_reasoning_effort=low -  <<< "reply READY"   # confirm a real completion
```
Windows sandbox gotcha (default home): if `workspace-write` fails (`ShellExecuteExW … 1223`), add to
`~/.codex/config.toml`:
```toml
[windows]
sandbox = "elevated"
```
(the noreen home already has this). Real bug-hunt runs use `-c model_reasoning_effort=xhigh`.

## agy (Antigravity, third vendor)
- Invoke with plain `agy --print`; a code-exec smoke (`python -c "print(6*7)"` → `42`) proves it runs
  real code. `--dangerously-skip-permissions` is blocked by the auto-mode classifier and not needed.
- `AGY_DRIVER_PATH` overrides the default `~/agy-driver/agy_driver.py` location.

## SSH to remote nodes (Tailscale fleet)
- Shared key: `~/.ssh/node2_ed25519` (store as `~/...` in config). Nodes per `overmind/cluster/nodes.seed.json`.
- `ssh → cmd.exe` on Windows remotes: **single-line `python -c "..."` only** (multi-line does not survive).
- First ping to a cold Tailscale peer may fail then succeed once the link is `active; direct` — not a
  real outage. ⚠ Confirm any specific IP against `nodes.seed.json` (there is a known pc2/baseimage IP
  discrepancy in the SOP).

## When to run
- **Before** any cross-vendor witness / bug-hunt / benchmark run that dispatches to Codex or agy.
- The preflight's degraded list feeds the cross-vendor stage's `AUTH_DEGRADED` handling: a degraded
  seat is never dispatched work and never counted as a live panel member.
