"""Declarative cluster config: load/save the node registry as JSON.

The fleet is config-driven. ``cluster/nodes.json`` holds the static node
declarations (reachability + capabilities); the live state (online/load) is never
persisted. A seed file (``nodes.seed.json``, committed) declares ``pc2`` + the
laptop so the cluster has a starting topology; the working copy lives under the
Overmind data dir and is edited by ``cluster add-node``.

``build_registry`` turns a config dict into a live ``NodeRegistry``. A node whose
name/host matches ``local_node`` (or the current hostname) is registered as the
**local** executor (runs in-process); every other node is **remote** (SSH).
"""
from __future__ import annotations

import json
import os
import socket
from pathlib import Path

from overmind.cluster.registry import Node, NodeRegistry


def default_config_path() -> Path:
    """Working cluster config path (env override → data dir → cwd fallback)."""
    override = os.environ.get("OVERMIND_CLUSTER_CONFIG")
    if override:
        return Path(override)
    try:
        from overmind.config import default_data_dir

        return default_data_dir() / "cluster" / "nodes.json"
    except Exception:  # noqa: BLE001 — config import shouldn't hard-fail this helper
        return Path.cwd() / "cluster-nodes.json"


def seed_config_path() -> Path:
    """The committed seed topology (pc2 + laptop)."""
    return Path(__file__).resolve().parent / "nodes.seed.json"


def load_config(path: Path | None = None) -> dict:
    """Load the cluster config dict; fall back to the committed seed if absent."""
    p = path or default_config_path()
    if not p.exists():
        seed = seed_config_path()
        if seed.exists():
            return json.loads(seed.read_text(encoding="utf-8"))
        return {"local_node": None, "nodes": []}
    return json.loads(p.read_text(encoding="utf-8"))


def save_config(config: dict, path: Path | None = None) -> Path:
    p = path or default_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    return p


def _is_local(node: Node, local_node: str | None, hostnames: set[str]) -> bool:
    if local_node and node.name == local_node:
        return True
    candidates = {c.lower() for c in (node.name, node.hostname, node.tailscale_ip, node.address) if c}
    return bool(candidates & {h.lower() for h in hostnames})


def build_registry(config: dict, *, this_hostname: str | None = None) -> NodeRegistry:
    """Build a live ``NodeRegistry`` from a config dict.

    The node identified as local (``config['local_node']`` or a host match)
    becomes the in-process ``LocalExecutor``; all others are SSH remotes.
    """
    local_node = config.get("local_node")
    host = this_hostname if this_hostname is not None else socket.gethostname()
    hostnames = {host} if host else set()

    reg = NodeRegistry()
    for nd in config.get("nodes", []):
        node = Node.from_dict(nd)
        if _is_local(node, local_node, hostnames):
            node = Node.from_dict({**nd, "kind": "local"})
        else:
            node = Node.from_dict({**nd, "kind": "remote"})
        reg.register(node)
    return reg


def add_node_to_config(config: dict, node: Node) -> dict:
    """Return a new config with ``node`` added/replaced (by name)."""
    nodes = [n for n in config.get("nodes", []) if n.get("name") != node.name]
    nodes.append(node.to_dict())
    nodes.sort(key=lambda n: n["name"])
    return {**config, "nodes": nodes}
