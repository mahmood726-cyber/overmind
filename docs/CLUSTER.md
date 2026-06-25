# CLUSTER.md — the self-load-balancing verification fleet

**Status (2026-06-25):** real. Replaces the previous `NotImplementedError` remote
stub (benchmark §5 #4). Node registry, health probing, capability-aware
load-balancing dispatch, and the SSH transport are implemented, unit-tested, and
**demonstrated live across pc2 + the laptop over Tailscale** (see *Demo* below).
Branch: `cluster-coordination-2026-06-25` (not merged).

> **Truth-first scope.** The scheduler/registry/transport/health logic is real and
> measured offline with injected SSH/ping (deterministic evals). Live multi-machine
> dispatch additionally needs the Tailscale nodes reachable and key-authorized —
> exercised by `overmind cluster health` / `dispatch`, not asserted in a unit test.
> Remote **load** is best-effort (`None` on Windows OpenSSH remotes); load-balancing
> uses in-flight job count as the primary signal, observed load as a tiebreak.

---

## 1. Architecture

```
overmind/cluster/
  registry.py    Node (static decl) + Capabilities + NodeState (live) + NodeRegistry
  config_io.py   JSON load/save; build_registry() localises the host node
  transport.py   SSHTransport + SSHExecutor (real, key-auth) + safety guards
  health.py      HealthProber: ping -> ssh -> capability refresh; online/offline
  scheduler.py   Job + JobScheduler + select_node (route + balance + cap + requeue)
  dispatch.py    Dispatcher (legacy single-node parallel fan-out; kept)
  delta_skip.py  DeltaSkipGate (content-hash gate, respects cross-repo impact #3d)
  onboard.py     onboard_node(): authorize key -> probe -> register
  cli_cluster.py overmind cluster <list|health|add-node|dispatch>
  nodes.seed.json  committed seed topology (pc2 + laptop)
```

**Routing decision (per job), in order:**

1. **Capability match** — node must have every `needs_engines` AND every
   `needs_data`. The data-volume check *is* data-locality: a job that needs the
   `ubcma` volume only goes to a node that has it. A job no online node can satisfy
   is reported **unschedulable** (never silently dropped or mis-routed).
2. **Least-loaded** — among capable online nodes with free capacity, pick the one
   with the lowest `running/max_parallel` (tiebreak: observed load, then name).
3. **Concurrency cap** — a node never exceeds `max_parallel` in-flight jobs, so
   dispatch can't recreate single-box saturation.

**Requeue-on-offline** — a node that fails mid-job with a connection-level error
(`RemoteTransientError`: ssh exit 255 / "connection refused" / timeout) is marked
**offline** and its job is requeued to another capable node (bounded by
`max_attempts`). Work is never lost; a real verification *failure* (non-transient)
is recorded, not requeued.

**Node lifecycle:** static declaration lives in `nodes.json`; live `NodeState`
(`status`, `load`, `running`, `observed` capabilities) lives only in memory and is
refreshed by the health prober. `effective_capabilities()` trusts the prober's
observed snapshot when present, else the declared config.

---

## 2. Safe-by-default (the standing constraints, enforced not assumed)

Enforced in `transport.assert_command_safe`, applied before any command leaves the
host (local runner and SSH path both call it):

- **No force-push.** `git push --force` / `--force-with-lease` / `-f` / `+<refspec>`
  are refused (`UnsafeCommandError`).
- **No Sentinel bypass.** `SENTINEL_BYPASS`, `--no-verify`, `--no-gpg-sign`,
  `-c core.hookspath` are refused — a dispatched job inherits the remote repo's
  pre-push Sentinel gating.
- **No secret leakage.** Only the SSH key **path** is used (`ssh -i <path>`); key
  material is never read or logged. Probe/error details carry no secrets.
- **Allowlisted commands.** The local runner additionally routes commands through
  `subprocess_utils.validate_command_prefix` (python/pytest/node/Rscript/… only).
- **Env-scrubbed subprocesses.** Local execution uses `verifier_popen_kwargs`
  (the same hardened, allow-listed env path the verifier uses).

---

## 3. The registry config (`nodes.json`)

`build_registry()` reads a JSON config; the node named in `local_node` (or one
whose host matches the current machine) is registered as the in-process
`LocalExecutor`, all others as SSH remotes. The committed seed
(`overmind/cluster/nodes.seed.json`) is used when no working config exists.

Working copy: `<OVERMIND_DATA_DIR>/cluster/nodes.json` (override with
`OVERMIND_CLUSTER_CONFIG`).

```json
{
  "local_node": "pc2",
  "nodes": [
    {
      "name": "pc2", "kind": "local", "max_parallel": 4,
      "tailscale_ip": "100.90.160.4", "ssh_user": "mahmo",
      "ssh_key_path": "~/.ssh/node2_ed25519",
      "capabilities": {"engines": ["claude","agy"], "data_volumes": ["ubcma","finerenone"], "cores": 4, "ram_gb": 17.0}
    },
    {
      "name": "mahmood", "kind": "remote", "max_parallel": 4,
      "tailscale_ip": "100.80.183.43", "ssh_user": "mahmo",
      "ssh_key_path": "~/.ssh/node2_ed25519",
      "capabilities": {"engines": [], "data_volumes": [], "cores": 0, "ram_gb": 0.0}
    }
  ]
}
```

Declared `engines`/`cores` are *intent*; the health prober refreshes them live
(`shutil.which` for engine presence, `os.cpu_count()` for cores). Declared
`data_volumes` are **config-trusted** (a tag like `ubcma` maps to a
machine-specific path the config owner asserts) and preserved across probes.

---

## 4. How to add a node (PC 3, PC 4, …)

One command — it authorizes the shared key, probes capabilities, and registers:

```bash
overmind cluster add-node \
  --name pc3 --host 100.x.y.z --user mahmo \
  --key ~/.ssh/node2_ed25519 \
  --engine claude --engine agy --data aact --max-parallel 4
```

What happens:

1. **Authorize** — appends `<key>.pub` to the new node's `~/.ssh/authorized_keys`
   (idempotent: skipped if already present). The *first* SSH may need an existing
   password/agent session; after that the node is key-only. Use `--no-authorize`
   if the node already trusts the key.
2. **Probe** — runs the real `HealthProber` (ping + ssh + capability refresh).
3. **Register** — writes the node into `nodes.json` (sorted, reversible).

> **Windows OpenSSH nuance.** The default key-authorization appends to
> `~/.ssh/authorized_keys` via a POSIX remote `sh`. A Windows OpenSSH *server* with
> an **administrator** account reads `%ProgramData%\ssh\administrators_authorized_keys`
> instead — for an admin remote, add the key there once manually, then use
> `--no-authorize`. Non-admin Windows accounts use `~/.ssh/authorized_keys` and work
> as-is. (pc2 → laptop key-auth already works in this configuration.)

---

## 5. How to dispatch

```bash
# 1. See the fleet (read-only)
overmind cluster list

# 2. Probe health (ping + ssh + refresh capabilities; marks online/offline)
overmind cluster health

# 3. Dispatch a batch of jobs (JSON)
overmind cluster dispatch --jobs jobs.json
```

`jobs.json` is a list of job objects:

```json
[
  {"repo": "ubcma-verify", "needs_data": ["ubcma"],
   "command": "python -m pytest -q"},
  {"repo": "codex-check", "needs_engines": ["codex"],
   "command": "python -m pytest tests/ -q", "cwd": "C:\\path\\to\\repo"}
]
```

- `needs_engines` / `needs_data` drive routing (capability + locality).
- `command` is the verification command — runs **locally** (hardened subprocess) on
  the local node, **over SSH** on a remote node. It must be allowlisted and is
  force-push/bypass checked before execution.
- `cwd` (optional) is the repo directory for local execution.
- `max_attempts` (optional, default 3) bounds requeue on transient failure.

Output: `assignments` (repo → node), per-job `results`, `attempts`, `requeued`,
`unschedulable`, `errors`.

---

## 6. Delta-skip (incremental, safe)

`DeltaSkipGate` skips repos whose content hash matches their last green verdict —
**except** a repo whose cross-repo dependency changed, which is pulled back in via
the #3d `ContractImpactGraph` (house lesson: never skip a repo whose upstream
dependency changed). Compose it before scheduling: gate → `to_run` set → dispatch.

---

## 7. Measured evals

`python -m evals.run_all` (offline, deterministic; injected ssh/ping):

| Eval | Metric | Result |
|------|--------|--------|
| `cluster_dispatch` | routing correct (capability+locality) | **100 %** |
| | data-locality respected | **True** |
| | load-balanced to least-loaded node | **True** |
| | uncapable job → unschedulable (not mis-routed) | **True** |
| | delta-skip: impacted dependents skipped | **0** (safe) |
| | requeue on offline node: work not lost | **True** (lands on healthy node) |
| | **all guarantees hold** | **True** |
| `cluster_delta_skip` | safe skip rate | **40 %** (2/5) |
| | impacted dependents skipped (graph gate) | **0** (naive hash-only: **3**) |
| | remote SSH transport real (runs, not stub) | **True** |

---

## 8. Live demo (pc2 + laptop, real Tailscale + SSH)

`overmind cluster health` → both online:

```
pc2     -> online | local node                       (4 cores; ubcma,finerenone)
mahmood -> online | ping+ssh ok; capabilities refreshed (8 cores; claude,codex,agy)
```

`overmind cluster dispatch --jobs demo-jobs.json` with a job needing `ubcma`
(only pc2 has it) and a job needing `codex` (only the laptop has the binary):

```
assignments: {"ubcma-verify": "pc2", "codex-verify": "mahmood"}
  ubcma-verify -> node pc2     | verdict PASS | ran_on pc2
  codex-verify -> node mahmood | verdict PASS | ran_on mahmood   # executed over SSH
errors: []   unschedulable: []
```

`ran_on` is the executing host's own `socket.gethostname()` — proof each job landed
on, and executed on, the correct node by capability/data-locality.
