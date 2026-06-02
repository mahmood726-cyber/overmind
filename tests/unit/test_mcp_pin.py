"""Tests for MCP descriptor pinning (P3-d)."""
from __future__ import annotations

import json
from pathlib import Path

from overmind.integrations.mcp_pin import check, collect_servers, pin


def _mcp(d: Path, name: str, command: str = "npx", args=None, env=None) -> None:
    d.mkdir(parents=True, exist_ok=True)
    server = {"command": command, "args": args or ["x"]}
    if env:
        server["env"] = env
    (d / ".mcp.json").write_text(json.dumps({"mcpServers": {name: server}}), encoding="utf-8")


def _collect(tmp, srv):
    # isolate from the real ~/.claude.json by pointing at a non-existent file
    return collect_servers(claude_json=tmp / "absent.json", scan_dirs=[str(srv)])


def test_pin_then_clean(tmp_path):
    srv = tmp_path / "srv"
    _mcp(srv, "gh")
    servers = _collect(tmp_path, srv)
    assert len(servers) == 1
    pinf = tmp_path / "pins.json"
    pin(servers, pinf)
    assert check(_collect(tmp_path, srv), pinf)["status"] == "ok"


def test_detects_changed_command(tmp_path):
    srv = tmp_path / "srv"
    _mcp(srv, "gh", command="npx")
    pinf = tmp_path / "pins.json"
    pin(_collect(tmp_path, srv), pinf)
    _mcp(srv, "gh", command="curl-evil")  # command silently changed
    r = check(_collect(tmp_path, srv), pinf)
    assert r["status"] == "drift"
    assert len(r["changed"]) == 1


def test_unpinned_status(tmp_path):
    srv = tmp_path / "srv"
    _mcp(srv, "gh")
    r = check(_collect(tmp_path, srv), tmp_path / "absent-pins.json")
    assert r["status"] == "unpinned"


def test_env_values_excluded_from_descriptor(tmp_path):
    srv = tmp_path / "srv"
    _mcp(srv, "s", env={"TOKEN": "secret123"})
    desc = next(iter(_collect(tmp_path, srv).values()))
    assert "secret123" not in json.dumps(desc)   # secret value never captured
    assert desc["env_keys"] == ["TOKEN"]          # key name only
