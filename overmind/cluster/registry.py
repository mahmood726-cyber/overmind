"""Node registry + executor interface for the verification cluster.

A *declarative* registry of cluster nodes. Each node carries enough to route work
to it: where it is (hostname / Tailscale IP), how to reach it (SSH user + key
path), what it can do (``Capabilities``: authed engines, present data volumes,
cores/RAM), plus a live, mutable ``NodeState`` (online/offline + current load +
in-flight job count) that the health prober and scheduler keep current.

The static declaration (``Node``) is immutable and serialisable to JSON so the
fleet is config-driven (``cluster/nodes.json``); the dynamic part (``NodeState``)
lives only in the running registry and is refreshed by ``health.HealthProber``.

Backward-compatible: the original minimal ``Node(name, kind, max_parallel,
address)`` and ``register_local`` / ``register_remote`` still work.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Protocol


# ── capabilities + static node declaration ──────────────────────────


@dataclass(frozen=True, slots=True)
class Capabilities:
    """What a node can run. All fields are *snapshots* — a node's authed engines
    or present data volumes can change, which is why the health prober can refresh
    an ``observed`` copy onto the live ``NodeState`` without mutating the node."""

    engines: tuple[str, ...] = ()        # authed CLI engines, e.g. ("claude","agy")
    data_volumes: tuple[str, ...] = ()   # logical data tags present, e.g. ("ubcma","aact")
    cores: int = 0
    ram_gb: float = 0.0

    def covers(self, *, engines: tuple[str, ...] = (), data: tuple[str, ...] = ()) -> bool:
        """True iff this node has every required engine AND every required data tag."""
        have_e = {e.lower() for e in self.engines}
        have_d = {d.lower() for d in self.data_volumes}
        return all(e.lower() in have_e for e in engines) and all(
            d.lower() in have_d for d in data
        )

    def to_dict(self) -> dict:
        return {
            "engines": list(self.engines),
            "data_volumes": list(self.data_volumes),
            "cores": self.cores,
            "ram_gb": self.ram_gb,
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "Capabilities":
        d = d or {}
        return cls(
            engines=tuple(d.get("engines", []) or []),
            data_volumes=tuple(d.get("data_volumes", []) or []),
            cores=int(d.get("cores", 0) or 0),
            ram_gb=float(d.get("ram_gb", 0.0) or 0.0),
        )


@dataclass(frozen=True, slots=True)
class Node:
    name: str
    kind: str = "local"          # "local" | "remote"
    max_parallel: int = 4
    address: str | None = None   # generic address (kept for back-compat)
    # Reachability (remote nodes):
    hostname: str | None = None
    tailscale_ip: str | None = None
    ssh_user: str | None = None
    ssh_key_path: str | None = None
    # Declared capabilities (the prober may refresh an observed copy onto state):
    capabilities: Capabilities = Capabilities()

    @property
    def ssh_host(self) -> str | None:
        """The host to SSH to: Tailscale IP preferred, else hostname/address."""
        return self.tailscale_ip or self.hostname or self.address

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "max_parallel": self.max_parallel,
            "address": self.address,
            "hostname": self.hostname,
            "tailscale_ip": self.tailscale_ip,
            "ssh_user": self.ssh_user,
            "ssh_key_path": self.ssh_key_path,
            "capabilities": self.capabilities.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Node":
        return cls(
            name=d["name"],
            kind=d.get("kind", "local"),
            max_parallel=int(d.get("max_parallel", 4)),
            address=d.get("address"),
            hostname=d.get("hostname"),
            tailscale_ip=d.get("tailscale_ip"),
            ssh_user=d.get("ssh_user"),
            ssh_key_path=d.get("ssh_key_path"),
            capabilities=Capabilities.from_dict(d.get("capabilities")),
        )


# ── live mutable per-node state ─────────────────────────────────────


@dataclass(slots=True)
class NodeState:
    """Dynamic, in-memory state for a node — never serialised to the static config."""

    status: str = "unknown"               # "online" | "offline" | "unknown"
    load: float | None = None             # load-per-core (1.0 == fully loaded); None == unknown
    running: int = 0                       # jobs currently dispatched to this node
    last_probe: str | None = None         # ISO timestamp of last health probe
    observed: Capabilities | None = None  # capabilities the prober actually saw
    detail: str = ""                       # human-readable probe detail (never a secret)

    @property
    def online(self) -> bool:
        return self.status == "online"

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "load": self.load,
            "running": self.running,
            "last_probe": self.last_probe,
            "observed": self.observed.to_dict() if self.observed else None,
            "detail": self.detail,
        }


# ── executor interface ──────────────────────────────────────────────


class Executor(Protocol):
    """Runs one verification job and returns a result dict.

    A job is ``{"repo": str, ...}``; the runner closure does the actual local
    verification (witnesses). A remote executor ignores the closure and runs the
    job's ``command`` over its transport instead. The executor only decides
    WHERE/HOW a job runs.
    """

    def run(self, job: dict, runner: Callable[[dict], dict]) -> dict: ...

    @property
    def name(self) -> str: ...


class LocalExecutor:
    """Real executor: runs the job in-process on this machine. Works today."""

    def __init__(self, name: str = "local") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def run(self, job: dict, runner: Callable[[dict], dict]) -> dict:
        result = runner(job)
        out = dict(result)
        out.setdefault("repo", job.get("repo"))
        out["executor"] = self._name
        out["node"] = self._name
        return out


# ── node registry ───────────────────────────────────────────────────


class NodeRegistry:
    """Declared executor nodes + their live state.

    Local nodes run in-process today. Remote nodes are reached over SSH by a real
    ``SSHExecutor`` (``overmind.cluster.transport``); the executor is built lazily
    so importing the registry never requires a transport. Until a remote node is
    probed it is ``status="unknown"`` and the scheduler treats only ``online``
    nodes as dispatch targets.
    """

    def __init__(self) -> None:
        self._nodes: list[Node] = []
        self._executors: dict[str, Executor] = {}
        self._state: dict[str, NodeState] = {}

    # -- registration -------------------------------------------------

    def register(self, node: Node) -> Node:
        """Register a fully-declared node (local or remote)."""
        if node.name in self._state:
            raise ValueError(f"node {node.name!r} already registered")
        self._nodes.append(node)
        self._state[node.name] = NodeState(
            status="online" if node.kind == "local" else "unknown",
            # A node's own declared cores are its initial capability snapshot.
            observed=node.capabilities if node.kind == "local" else None,
        )
        if node.kind == "local":
            self._executors[node.name] = LocalExecutor(name=node.name)
        else:
            self._executors[node.name] = self._build_remote_executor(node)
        return node

    def register_local(
        self,
        name: str = "local",
        max_parallel: int = 4,
        *,
        capabilities: Capabilities | None = None,
    ) -> Node:
        node = Node(
            name=name,
            kind="local",
            max_parallel=max_parallel,
            capabilities=capabilities or Capabilities(),
        )
        return self.register(node)

    def register_remote(
        self,
        name: str,
        address: str,
        max_parallel: int = 4,
        *,
        ssh_user: str | None = None,
        ssh_key_path: str | None = None,
        tailscale_ip: str | None = None,
        hostname: str | None = None,
        capabilities: Capabilities | None = None,
    ) -> Node:
        node = Node(
            name=name,
            kind="remote",
            max_parallel=max_parallel,
            address=address,
            hostname=hostname,
            tailscale_ip=tailscale_ip or address,
            ssh_user=ssh_user,
            ssh_key_path=ssh_key_path,
            capabilities=capabilities or Capabilities(),
        )
        return self.register(node)

    def _build_remote_executor(self, node: Node) -> Executor:
        # Lazy import: keeps the registry importable with no transport dependency.
        from overmind.cluster.transport import SSHExecutor

        return SSHExecutor(node)

    # -- accessors ----------------------------------------------------

    @property
    def nodes(self) -> list[Node]:
        return list(self._nodes)

    def get(self, name: str) -> Node:
        for n in self._nodes:
            if n.name == name:
                return n
        raise KeyError(name)

    def state(self, name: str) -> NodeState:
        return self._state[name]

    def local_nodes(self) -> list[Node]:
        return [n for n in self._nodes if n.kind == "local"]

    def remote_nodes(self) -> list[Node]:
        return [n for n in self._nodes if n.kind == "remote"]

    def online_nodes(self) -> list[Node]:
        return [n for n in self._nodes if self._state[n.name].online]

    def executor_for(self, node_name: str) -> Executor:
        return self._executors[node_name]

    def set_executor(self, node_name: str, executor: Executor) -> None:
        """Override a node's executor (e.g. inject a custom SSH transport for a
        test/eval, or swap in an alternative remote transport at runtime)."""
        if node_name not in self._state:
            raise KeyError(node_name)
        self._executors[node_name] = executor

    def total_parallelism(self, local_only: bool = True) -> int:
        nodes = self.local_nodes() if local_only else self._nodes
        return sum(n.max_parallel for n in nodes)

    # -- live state mutation (used by the health prober + scheduler) --

    def set_status(self, name: str, status: str, *, detail: str = "", load: float | None = None) -> None:
        st = self._state[name]
        st.status = status
        if detail:
            st.detail = detail
        if load is not None:
            st.load = load

    def set_observed_capabilities(self, name: str, caps: Capabilities) -> None:
        self._state[name].observed = caps

    def effective_capabilities(self, name: str) -> Capabilities:
        """The capabilities the scheduler should trust: the prober's observed
        snapshot if available, else the declared ones."""
        st = self._state[name]
        return st.observed if st.observed is not None else self.get(name).capabilities

    def capable_online_nodes(
        self, *, engines: tuple[str, ...] = (), data: tuple[str, ...] = ()
    ) -> list[Node]:
        """Online nodes whose *effective* capabilities cover the requirement."""
        out = []
        for n in self.online_nodes():
            if self.effective_capabilities(n.name).covers(engines=engines, data=data):
                out.append(n)
        return out

    def mark_running_delta(self, name: str, delta: int) -> None:
        st = self._state[name]
        st.running = max(0, st.running + delta)

    def free_capacity(self, name: str) -> int:
        return max(0, self.get(name).max_parallel - self._state[name].running)

    # -- (de)serialisation of the static declaration ------------------

    def to_dict(self) -> dict:
        return {"nodes": [n.to_dict() for n in self._nodes]}

    @classmethod
    def from_dict(cls, d: dict) -> "NodeRegistry":
        reg = cls()
        for nd in d.get("nodes", []):
            reg.register(Node.from_dict(nd))
        return reg

    def snapshot(self) -> list[dict]:
        """A combined static+live view, for `cluster list` / observability."""
        out = []
        for n in self._nodes:
            row = n.to_dict()
            row["state"] = self._state[n.name].to_dict()
            row["effective_capabilities"] = self.effective_capabilities(n.name).to_dict()
            out.append(row)
        return out
