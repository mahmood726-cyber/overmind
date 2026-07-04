# SOP — Codex / agy Fleet Auth Recipe

> **Version:** v1.0 · **Status:** verified 2026-07-04 (both Codex seats re-authed mid-session; agy live)
> **Owner:** fleet/infra · **Change log:** v1.0 — from the two-seat + post-reauth + third-vendor reports.

## Purpose
Bring the non-Claude vendors (**OpenAI Codex**, **Antigravity `agy`**) online for a cross-vendor witness
([[Cross-Vendor-Witness-SOP]]). Codex OAuth cannot be restored headlessly — this records the exact recipe.

## Codex — two seats, per-seat CODEX_HOME
| Seat | `CODEX_HOME` | Account |
|---|---|---|
| **A / default** | `C:\Users\mahmo\.codex` | `mahmood726` (gpt-5.5) |
| **B / Noreen** | `C:\Users\mahmo\.codex-noreen` | 2nd seat |

- **Auth is per-`CODEX_HOME`.** Set `CODEX_HOME` before `codex login` / `codex exec` to target a seat.
- **Re-auth is interactive-only.** When a seat is `401 / refresh token revoked`, the *only* fix is an
  interactive `codex login` (browser OAuth) **on pc1** — a headless subprocess cannot re-mint the token.
  Today both seats were 401 until Mahmood re-logged in mid-session; then both `codex exec` smoke tests
  returned real completions. (Root cause: the shared `mahmood726` subscription refresh token was revoked
  globally — the account is not deleted, so `codex login` restores it.)
- **Windows sandbox gotcha.** On the default home the `workspace-write` sandbox helper fails
  (`ShellExecuteExW … 1223`), blocking `python`/`git` launches. **Runtime fix:**
  `--dangerously-bypass-approvals-and-sandbox` (trusted local repo). **Permanent fix:** add to
  `~/.codex/config.toml`:
  ```toml
  [windows]
  sandbox = "elevated"
  ```
  (the noreen home already has this.)
- **Other flags:** `codex exec` with `-c model_reasoning_effort=xhigh` for the real run. `--skip-git-repo-check`
  is a known codex flag for running outside a git repo (mentioned in the fleet brief; **not exercised in
  today's reports** — verify before relying on it).

## agy (Antigravity CLI) — third vendor
- **Version verified today:** `agy v1.0.16`, pc1, authenticated. Runs as an **independent THIRD vendor.**
- Invoke with plain **`agy --print`** — the auto-mode classifier blocked `--dangerously-skip-permissions`
  and it was **not needed**: a smoke test `python -c "print(6*7)"` returned `42`, proving `--print` mode
  executes real code.
- Each job writes its own raw artifact (`verification/agy_job{1,2}_raw.md`).

## SSH to remote nodes (Tailscale fleet)
- **Shared key:** `~/.ssh/node2_ed25519` for all nodes. *(Store as `~/...` in config — a hardcoded
  `C:\Users\mahmo\...` path is a Sentinel BLOCK.)*
- **Nodes** (per memory + `overmind/cluster/nodes.seed.json`): **pc2** (local, ssh `mahmo`, engines
  claude+agy), **mahmood** laptop (`100.80.183.43`, ssh `mahmo`, engines claude/codex/agy), **baseimage**
  (`100.127.107.46`, ssh `user`, engines claude/codex; python is a Store stub → python capability false).
  > ⚠ **IP discrepancy to resolve:** today's Codex report calls `100.127.107.46` "pc2" while the cluster
  > memory maps that IP to *baseimage* and gives pc2 `100.90.160.4`. Confirm against
  > `nodes.seed.json` before scripting against a specific IP.
- **`ssh → cmd.exe` on Windows remotes:** multi-line `python -c "..."` does **not** survive — use
  **single-line only**. First ping to a cold Tailscale peer can fail then succeed once the link goes
  `active; direct` — not a real outage.
- **Today's state:** SSH to the laptop `100.80.183.43` and pc2 both **denied publickey** non-interactively
  (the memory note that "laptop Codex authenticates headless over SSH" relied on a key not accepted from
  this host) — hence the interactive pc1 re-login was the unblock.

## Fleet auth state — 2026-07-04 (snapshot)
| Vendor / path | State |
|---|---|
| Codex Seat A (`~/.codex`) | 401 → **re-authed mid-session** (token landed ~11:56) |
| Codex Seat B (`~/.codex-noreen`) | revoked → **re-minted** after `codex logout`→`codex login` |
| agy (pc1) | **live** (v1.0.16, `--print`, `42` smoke) |
| Claude-in-subprocess | needs `ANTHROPIC_API_KEY` (per frontier-closing §5) |
| SSH to laptop / pc2 | publickey denied non-interactively this session |

## Ties to
[[Cross-Vendor-Witness-SOP]] · [[Decisions-Log-2026-07-04]] (fleet auth decision) · [[_SOPs-MOC]].
