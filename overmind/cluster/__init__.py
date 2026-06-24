"""Codified multi-node verification capability (node registry + dispatch).

Truth-first status (see docs/SYSTEMS-BENCHMARK-VS-FRONTIER.md §0): the
"multi-node Tailscale cluster" was previously an **undocumented aspiration** — no
registry, no dispatch, no remote runner in code. This package converts it into a
*codified capability*:

  * ``NodeRegistry``    — declared executor nodes (local now; remote later).
  * ``Dispatcher``      — fans verification jobs out across nodes in parallel.
  * ``LocalExecutor``   — a REAL executor that runs jobs in-process / local
                          subprocesses (works today, no network).
  * ``DeltaSkipGate``   — a content-hash gate that skips repos unchanged since
                          their last green verdict, **while never skipping a repo
                          whose cross-repo dependency changed** (uses the #3d
                          ContractImpactGraph).

Explicitly DEFERRED and marked as such (not claimed as shipped): the actual
remote *transport* over Tailscale (an ``SSHExecutor`` / ``HTTPExecutor`` talking
to remote nodes). The interface (``Executor``) is ready so that transport can land
without touching the dispatcher or gate; until it does, ``NodeRegistry`` holds
only local nodes and ``RemoteExecutor`` raises ``NotImplementedError`` with a
clear deferred message rather than pretending.
"""
from overmind.cluster.registry import NodeRegistry, Node, Executor, LocalExecutor, RemoteExecutor
from overmind.cluster.dispatch import Dispatcher, DispatchResult
from overmind.cluster.delta_skip import DeltaSkipGate, SkipDecision

__all__ = [
    "NodeRegistry", "Node", "Executor", "LocalExecutor", "RemoteExecutor",
    "Dispatcher", "DispatchResult",
    "DeltaSkipGate", "SkipDecision",
]
