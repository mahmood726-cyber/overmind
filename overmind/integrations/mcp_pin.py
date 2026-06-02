"""MCP descriptor pinning (Phase 3): pin local MCP server definitions and detect
drift — a guardrail against silent supply-chain / descriptor changes (the
"MCP descriptor injection" risk in lessons.md).

Collects server defs from ``~/.claude.json`` (``mcpServers``) and any ``.mcp.json``
files under ``--scan`` dirs, hashes each server's stable descriptor
(``type/command/args/url`` + env KEY names — never env values), pins them to a
manifest, and reports added / removed / changed servers on re-run.

Honest boundary: this covers **locally-configured** MCP servers and plugin
``.mcp.json`` definitions only. **claude.ai cloud connectors** (Gmail, Drive,
PubMed, …) are managed server-side and are NOT pinnable from here.

Stdlib only, deterministic, read-only except the explicit ``--update`` pin write.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _descriptor(server: dict) -> dict:
    """Stable, secret-free descriptor of one server definition."""
    return {
        "type": server.get("type", "stdio"),
        "command": server.get("command"),
        "args": list(server.get("args", []) or []),
        "url": server.get("url"),
        # KEY names only — never env/header VALUES (they hold tokens).
        "env_keys": sorted((server.get("env") or {}).keys()),
        "header_keys": sorted((server.get("headers") or {}).keys()),
    }


def _looks_like_server(v) -> bool:
    return isinstance(v, dict) and any(k in v for k in ("command", "url", "type"))


def _hash(desc: dict) -> str:
    return hashlib.sha256(json.dumps(desc, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except (OSError, json.JSONDecodeError):
        return {}


def collect_servers(claude_json: Path | None = None,
                    scan_dirs: list[str] | None = None) -> dict[str, dict]:
    servers: dict[str, dict] = {}
    cj = claude_json or (Path.home() / ".claude.json")
    if cj.exists():
        for name, s in (_load_json(cj).get("mcpServers") or {}).items():
            if isinstance(s, dict):
                servers[f"{cj.name}::{name}"] = _descriptor(s)
    for d in scan_dirs or []:
        root = Path(d)
        if not root.exists():
            continue
        for f in sorted(root.rglob(".mcp.json")):
            data = _load_json(f)
            # Two shapes: {"mcpServers": {name: def}} (claude config style) or a
            # flat {name: def, ...} (plugin .mcp.json style).
            entries = data.get("mcpServers")
            if not isinstance(entries, dict):
                entries = {k: v for k, v in data.items() if _looks_like_server(v)}
            for name, s in entries.items():
                if isinstance(s, dict):
                    servers[f"{f}::{name}"] = _descriptor(s)
    return servers


def build_manifest(servers: dict[str, dict]) -> dict:
    return {k: {"hash": _hash(v), "descriptor": v} for k, v in servers.items()}


def pin(servers: dict[str, dict], pin_path: Path) -> dict:
    pin_path.parent.mkdir(parents=True, exist_ok=True)
    pin_path.write_text(json.dumps(build_manifest(servers), indent=2, sort_keys=True),
                        encoding="utf-8")
    return {"action": "pinned", "servers": len(servers), "pin_file": str(pin_path),
            "keys": sorted(servers)}


def check(servers: dict[str, dict], pin_path: Path) -> dict:
    cur = build_manifest(servers)
    if not pin_path.exists():
        return {"status": "unpinned", "servers": len(cur),
                "note": "no pin manifest yet — run `mcp-pin --update` to establish a baseline"}
    pinned = _load_json(pin_path)
    added = sorted(k for k in cur if k not in pinned)
    removed = sorted(k for k in pinned if k not in cur)
    changed = sorted(k for k in cur if k in pinned and cur[k]["hash"] != pinned[k]["hash"])
    status = "ok" if not (added or removed or changed) else "drift"
    return {"status": status, "servers": len(cur),
            "added": added, "removed": removed, "changed": changed}
