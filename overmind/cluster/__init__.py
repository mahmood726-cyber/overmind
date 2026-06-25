"""Self-load-balancing verification cluster (node registry + scheduler + transport).

A real multi-machine fleet over Tailscale, replacing the manual-SSH workflow and
the previous ``NotImplementedError`` remote stub. Pieces:

  * ``NodeRegistry`` / ``Node`` / ``Capabilities`` / ``NodeState`` — a declarative,
    JSON-backed registry of nodes (reachability + engines/data/cores + live load).
  * ``HealthProber`` — ping + ssh + capability refresh; marks nodes online/offline.
  * ``JobScheduler`` — capability- and data-locality-aware routing to the
    least-loaded online node, per-node concurrency caps, and requeue-on-offline.
  * ``SSHExecutor`` / ``SSHTransport`` — the REAL remote transport (key auth),
    safe-by-default: force-push and Sentinel-bypass are refused before a command
    leaves the host; only key *paths* are used, never key material.
  * ``LocalExecutor`` — in-process executor (works today, no network).
  * ``DeltaSkipGate`` — content-hash gate that skips repos unchanged since their
    last green verdict, while **never** skipping a repo whose cross-repo dependency
    changed (routes the changed set through the #3d ``ContractImpactGraph``).
  * ``onboard_node`` — one-command ``cluster add-node`` (authorize key → probe →
    register), so adding PCs 3 and 4 is a single command.
  * ``Dispatcher`` — the original single-node parallel fan-out (kept for back-compat).

Honest status: the local capability and the full scheduler/registry/transport logic
are real and measured offline (injectable ssh/ping). Live multi-machine dispatch
additionally requires the Tailscale nodes to be reachable and key-authorized; that
runtime is exercised by ``overmind cluster health`` / ``dispatch``, not asserted here.
"""
from overmind.cluster.registry import (
    Capabilities,
    Executor,
    LocalExecutor,
    Node,
    NodeRegistry,
    NodeState,
)
from overmind.cluster.transport import (
    RemoteExecutor,
    RemoteTransientError,
    SSHExecutor,
    SSHTransport,
    UnsafeCommandError,
    assert_command_safe,
    build_ssh_argv,
)
from overmind.cluster.health import HealthProber, ProbeResult, build_probe_command
from overmind.cluster.scheduler import Job, JobScheduler, ScheduleResult, select_node
from overmind.cluster.dispatch import Dispatcher, DispatchResult
from overmind.cluster.delta_skip import DeltaSkipGate, SkipDecision
from overmind.cluster.onboard import OnboardResult, onboard_node
from overmind.cluster.config_io import (
    add_node_to_config,
    build_registry,
    default_config_path,
    load_config,
    save_config,
    seed_config_path,
)

__all__ = [
    # registry
    "NodeRegistry", "Node", "Capabilities", "NodeState", "Executor", "LocalExecutor",
    # transport
    "SSHExecutor", "SSHTransport", "RemoteExecutor", "RemoteTransientError",
    "UnsafeCommandError", "assert_command_safe", "build_ssh_argv",
    # health
    "HealthProber", "ProbeResult", "build_probe_command",
    # scheduler
    "Job", "JobScheduler", "ScheduleResult", "select_node",
    # dispatch (legacy parallel fan-out)
    "Dispatcher", "DispatchResult",
    # delta-skip
    "DeltaSkipGate", "SkipDecision",
    # onboarding
    "onboard_node", "OnboardResult",
    # config
    "load_config", "save_config", "build_registry", "add_node_to_config",
    "default_config_path", "seed_config_path",
]
