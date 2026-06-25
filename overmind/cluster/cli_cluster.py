"""CLI handlers for ``overmind cluster <list|health|add-node|dispatch>``.

Thin glue over the cluster package. ``list`` / ``health`` are read-only; ``add-node``
persists the registry config; ``dispatch`` schedules jobs across online nodes
(local jobs run in-process via a safe local command runner, remote jobs run over
SSH). No secrets are printed — only key *paths* and node addresses appear.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from overmind.cluster.config_io import (
    add_node_to_config,
    build_registry,
    default_config_path,
    load_config,
    save_config,
)
from overmind.cluster.health import HealthProber
from overmind.cluster.registry import Capabilities, NodeRegistry
from overmind.cluster.scheduler import Job, JobScheduler
from overmind.cluster.transport import UnsafeCommandError, assert_command_safe, parse_result_line
from overmind.subprocess_utils import (
    split_command,
    validate_command_prefix,
    verifier_popen_kwargs,
)


def _config_path(args) -> Path:
    return Path(args.cluster_config) if getattr(args, "cluster_config", None) else default_config_path()


def cmd_list(args) -> dict:
    cfg = load_config(_config_path(args))
    reg = build_registry(cfg)
    return {"config_path": str(_config_path(args)), "local_node": cfg.get("local_node"),
            "nodes": reg.snapshot()}


def cmd_health(args) -> dict:
    cfg = load_config(_config_path(args))
    reg = build_registry(cfg)
    results = HealthProber().refresh(reg)
    return {
        "probed": [
            {"node": r.node, "status": r.status, "load": r.load, "detail": r.detail}
            for r in results
        ],
        "online": [n.name for n in reg.online_nodes()],
        "nodes": reg.snapshot(),
    }


def cmd_add_node(args) -> dict:
    from overmind.cluster.onboard import onboard_node

    declared = Capabilities(
        engines=tuple(args.engine or ()),
        data_volumes=tuple(args.data or ()),
    )
    res = onboard_node(
        name=args.name,
        host=args.host,
        ssh_user=args.user,
        ssh_key_path=args.key,
        tailscale_ip=args.ip,
        max_parallel=args.max_parallel,
        declared=declared,
        authorize=not args.no_authorize,
    )
    path = _config_path(args)
    cfg = load_config(path)
    if cfg.get("local_node") is None:
        cfg["local_node"] = None
    cfg = add_node_to_config(cfg, res.node)
    save_config(cfg, path)
    out = res.to_dict()
    out["registered"] = True
    out["config_path"] = str(path)
    return out


def _make_local_runner() -> "callable":
    """A real local verification runner: runs the job's command in its repo dir
    via the hardened subprocess path (env-scrubbed, allowlisted prefix)."""

    def run(job: dict) -> dict:
        repo = job.get("repo")
        cmd = job.get("command")
        cwd = job.get("cwd") or os.getcwd()
        if not cmd:
            return {"repo": repo, "verdict": "SKIP", "detail": "no command"}
        try:
            assert_command_safe(cmd)
        except UnsafeCommandError as exc:
            return {"repo": repo, "verdict": "FAIL", "detail": f"unsafe: {exc}"}
        if not validate_command_prefix(cmd, cwd=cwd):
            return {"repo": repo, "verdict": "FAIL", "detail": "command prefix not allowlisted"}
        argv = split_command(cmd)
        kwargs = verifier_popen_kwargs(cwd)
        try:
            cp = subprocess.run(argv, timeout=float(job.get("timeout", 900.0)), **kwargs)
        except subprocess.TimeoutExpired:
            return {"repo": repo, "verdict": "FAIL", "detail": "local command timed out"}
        parsed = parse_result_line(cp.stdout or "") or {}
        out = {"repo": repo, **parsed}
        out.setdefault("verdict", "PASS" if cp.returncode == 0 else "FAIL")
        out["returncode"] = cp.returncode
        return out

    return run


def cmd_dispatch(args) -> dict:
    cfg = load_config(_config_path(args))
    reg = build_registry(cfg)
    if not args.no_health:
        HealthProber().refresh(reg)

    jobs_spec = json.loads(Path(args.jobs).read_text(encoding="utf-8"))
    if not isinstance(jobs_spec, list):
        raise SystemExit("--jobs must be a JSON list of job objects")
    jobs = [
        Job(
            repo=j["repo"],
            needs_engines=tuple(j.get("needs_engines", []) or []),
            needs_data=tuple(j.get("needs_data", []) or []),
            command=j.get("command"),
            timeout=float(j.get("timeout", 900.0)),
            max_attempts=int(j.get("max_attempts", 3)),
            payload={k: v for k, v in j.items() if k == "cwd"},
        )
        for j in jobs_spec
    ]
    res = JobScheduler(reg).schedule(jobs, _make_local_runner())
    return {
        "online_nodes": [n.name for n in reg.online_nodes()],
        "assignments": res.assignments,
        "results": res.results,
        "attempts": res.attempts,
        "requeued": res.requeued,
        "unschedulable": res.unschedulable,
        "errors": res.errors,
    }


def dispatch(args) -> dict:
    """Route ``overmind cluster <action>`` to its handler."""
    action = args.cluster_action
    if action == "list":
        return cmd_list(args)
    if action == "health":
        return cmd_health(args)
    if action == "add-node":
        return cmd_add_node(args)
    if action == "dispatch":
        return cmd_dispatch(args)
    raise SystemExit(f"unknown cluster action: {action!r}")
