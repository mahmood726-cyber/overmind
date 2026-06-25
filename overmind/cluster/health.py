"""Node health probe: reachability + live load + capability refresh.

``HealthProber.probe(node)`` decides whether a node is ``online`` and refreshes
its volatile capabilities (authed engines, cores, load) onto the registry's live
``NodeState``. The flow for a remote node is:

  1. **ping** the Tailscale IP (fast reachability gate),
  2. **ssh echo** over key auth (confirms the transport + auth actually work),
  3. **ssh probe** a small ``python -c`` one-liner that returns JSON
     ``{cores, load, engines}`` — re-detecting which CLI engines are present and
     the current load, so routing reflects reality rather than stale config.

Declared *data volumes* are trusted from config (a data tag like ``ubcma`` maps to
a machine-specific path that the config owner asserts); engines/cores/load are
re-probed live. Local nodes are always online; their load comes from ``psutil``
when available.

Everything external (ping, ssh) is injectable so the prober is fully testable
offline and the evals are deterministic. No secrets are read or logged — only the
SSH key *path* is used, by the transport.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

from overmind.cluster.registry import Capabilities, Node, NodeRegistry
from overmind.cluster.transport import SSHTransport

_DEFAULT_ENGINES = ("claude", "codex", "agy", "gemini")

# A portable probe: python is the house runtime on every node. It MUST be a single
# line — a multi-line `python -c` argument does not survive `ssh -> cmd.exe` on a
# Windows OpenSSH remote (embedded newlines truncate the command). Load is left to
# the load-balancer's in-flight-job count (remote load is best-effort/None here);
# cores + engine presence are what routing needs.
_PROBE_PY = (
    "import json,os,shutil;"
    "print(json.dumps({{'cores':os.cpu_count() or 0,'load':None,"
    "'engines':[e for e in {engines!r} if shutil.which(e)]}}))"
)


def build_probe_command(engines: tuple[str, ...] = _DEFAULT_ENGINES) -> str:
    """A single-line ``python -c`` command that prints one JSON capability line."""
    body = _PROBE_PY.format(engines=list(engines))
    return f'python -c {_shquote(body)}'


def _shquote(s: str) -> str:
    # Double-quote for the remote shell, escaping inner double-quotes/backslashes.
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


PingFn = Callable[[str, float], bool]
LocalLoadFn = Callable[[], "float | None"]


def _default_ping(host: str, timeout_s: float) -> bool:
    if os.name == "nt":
        argv = ["ping", "-n", "1", "-w", str(int(timeout_s * 1000)), host]
    else:
        argv = ["ping", "-c", "1", "-W", str(max(1, int(timeout_s))), host]
    try:
        cp = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s + 2)
        return cp.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def _default_local_load() -> float | None:
    try:
        import psutil
    except Exception:  # noqa: BLE001 — psutil optional at probe time
        return None
    try:
        if hasattr(psutil, "getloadavg"):
            return psutil.getloadavg()[0] / (os.cpu_count() or 1)
        return psutil.cpu_percent(interval=0.1) / 100.0
    except Exception:  # noqa: BLE001
        return None


@dataclass(slots=True)
class ProbeResult:
    node: str
    status: str                       # "online" | "offline"
    load: float | None = None
    observed: Capabilities | None = None
    detail: str = ""


class HealthProber:
    """Probes nodes and writes status/load/observed-capabilities back to a registry."""

    def __init__(
        self,
        *,
        transport: SSHTransport | None = None,
        ping_fn: PingFn | None = None,
        local_load_fn: LocalLoadFn | None = None,
        engines: tuple[str, ...] = _DEFAULT_ENGINES,
        ping_timeout_s: float = 3.0,
        ssh_timeout_s: float = 12.0,
    ) -> None:
        self._transport = transport or SSHTransport()
        self._ping = ping_fn or _default_ping
        self._local_load = local_load_fn or _default_local_load
        self._engines = engines
        self._ping_timeout = ping_timeout_s
        self._ssh_timeout = ssh_timeout_s

    def _now(self) -> str:
        return datetime.now(UTC).replace(microsecond=0).isoformat()

    def probe(self, node: Node) -> ProbeResult:
        if node.kind == "local":
            load = self._local_load()
            return ProbeResult(
                node=node.name, status="online", load=load,
                observed=node.capabilities, detail="local node",
            )
        return self._probe_remote(node)

    def _probe_remote(self, node: Node) -> ProbeResult:
        host = node.ssh_host
        if not host:
            return ProbeResult(node=node.name, status="offline", detail="no ssh host configured")

        if not self._ping(host, self._ping_timeout):
            return ProbeResult(node=node.name, status="offline", detail=f"ping {host} failed")

        probe_cmd = build_probe_command(self._engines)
        res = self._transport.run(node, probe_cmd, timeout=self._ssh_timeout)
        if res.transient:
            return ProbeResult(
                node=node.name, status="offline",
                detail=f"ssh transient (rc={res.returncode})",
            )
        if res.returncode != 0:
            return ProbeResult(
                node=node.name, status="offline",
                detail=f"probe command failed (rc={res.returncode})",
            )

        observed = self._parse_probe(node, res.stdout)
        load = observed[1]
        caps = observed[0]
        return ProbeResult(
            node=node.name, status="online", load=load, observed=caps,
            detail="ping+ssh ok; capabilities refreshed",
        )

    def _parse_probe(self, node: Node, stdout: str) -> tuple[Capabilities, float | None]:
        """Parse the JSON probe line; fall back to declared caps on any malformity.

        Declared data volumes are preserved (config-trusted); engines/cores/load
        come from the live probe.
        """
        declared = node.capabilities
        for line in reversed([ln.strip() for ln in (stdout or "").splitlines() if ln.strip()]):
            if not (line.startswith("{") and line.endswith("}")):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            engines = tuple(obj.get("engines", []) or [])
            cores = int(obj.get("cores", 0) or declared.cores or 0)
            load = obj.get("load")
            load = float(load) if isinstance(load, (int, float)) else None
            caps = Capabilities(
                engines=engines,
                data_volumes=declared.data_volumes,   # config-trusted
                cores=cores,
                ram_gb=declared.ram_gb,
            )
            return caps, load
        # Unparseable: keep declared capabilities, unknown load.
        return declared, None

    # -- registry integration ----------------------------------------

    def refresh(self, registry: NodeRegistry) -> list[ProbeResult]:
        """Probe every node and write status/load/observed-capabilities back."""
        results: list[ProbeResult] = []
        for node in registry.nodes:
            pr = self.probe(node)
            registry.set_status(node.name, pr.status, detail=pr.detail, load=pr.load)
            registry.state(node.name).last_probe = self._now()
            if pr.observed is not None:
                registry.set_observed_capabilities(node.name, pr.observed)
            results.append(pr)
        return results
