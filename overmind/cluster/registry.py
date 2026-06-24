"""Node registry + executor interface for the verification cluster."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol


@dataclass(slots=True, frozen=True)
class Node:
    name: str
    kind: str            # "local" | "remote"
    max_parallel: int = 4
    address: str | None = None   # e.g. tailscale host for a future remote node


class Executor(Protocol):
    """Runs one verification job and returns a result dict.

    A job is ``{"repo": str, ...}``; the runner closure does the actual
    verification (witnesses). The executor only decides WHERE/HOW it runs.
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
        return out


class RemoteExecutor:
    """Placeholder for the DEFERRED remote transport (SSH/HTTP over Tailscale).

    The interface is in place so a real transport can land without changing the
    Dispatcher or DeltaSkipGate. Until then it raises with a clear, honest message
    rather than silently pretending to run remotely.
    """

    def __init__(self, node: Node) -> None:
        self.node = node

    @property
    def name(self) -> str:
        return f"remote:{self.node.name}"

    def run(self, job: dict, runner: Callable[[dict], dict]) -> dict:
        raise NotImplementedError(
            f"remote executor for node {self.node.name!r} is DEFERRED — the "
            "Tailscale transport is not implemented yet. Use a LocalExecutor, or "
            "implement SSH/HTTP dispatch against the Executor interface."
        )


class NodeRegistry:
    """Declared executor nodes. Local-only today; remote nodes are accepted but
    flagged so the dispatcher (and a human) can see what is real vs deferred."""

    def __init__(self) -> None:
        self._nodes: list[Node] = []
        self._executors: dict[str, Executor] = {}

    def register_local(self, name: str = "local", max_parallel: int = 4) -> Node:
        node = Node(name=name, kind="local", max_parallel=max_parallel)
        self._nodes.append(node)
        self._executors[name] = LocalExecutor(name=name)
        return node

    def register_remote(self, name: str, address: str, max_parallel: int = 4) -> Node:
        """Declare a remote node. Its executor is the DEFERRED RemoteExecutor —
        registering it does not make remote dispatch real, it just records intent."""
        node = Node(name=name, kind="remote", max_parallel=max_parallel, address=address)
        self._nodes.append(node)
        self._executors[name] = RemoteExecutor(node)
        return node

    @property
    def nodes(self) -> list[Node]:
        return list(self._nodes)

    def local_nodes(self) -> list[Node]:
        return [n for n in self._nodes if n.kind == "local"]

    def executor_for(self, node_name: str) -> Executor:
        return self._executors[node_name]

    def total_parallelism(self, local_only: bool = True) -> int:
        nodes = self.local_nodes() if local_only else self._nodes
        return sum(n.max_parallel for n in nodes)
