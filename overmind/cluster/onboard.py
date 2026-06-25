"""One-command node onboarding: authorize key → probe → register.

``cluster add-node`` turns "add PC 3" into a single command instead of manual SSH:

  1. **Authorize** the shared public key on the new node's ``authorized_keys``
     (idempotent — never appends a duplicate), so subsequent dispatch is key-auth.
  2. **Probe** it with the real ``HealthProber`` (ping + ssh + capability refresh).
  3. **Register** it into the cluster config (``cluster/nodes.json``).

The key-authorization step needs an initial trust path to the new node. The first
SSH (to install the key) may require an existing password/agent session; that is
the one manual moment, after which the node is key-only. Everything is injectable
(``authorize_fn`` / prober transport) so onboarding is testable offline and the
key material is never read or logged — only the public-key *path* is used.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from overmind.cluster.health import HealthProber, ProbeResult
from overmind.cluster.registry import Capabilities, Node


@dataclass(slots=True)
class OnboardResult:
    node: Node
    key_authorized: bool
    probe: ProbeResult
    registered: bool = False
    detail: str = ""

    @property
    def online(self) -> bool:
        return self.probe.status == "online"

    def to_dict(self) -> dict:
        return {
            "node": self.node.to_dict(),
            "key_authorized": self.key_authorized,
            "online": self.online,
            "registered": self.registered,
            "probe": {"status": self.probe.status, "detail": self.probe.detail, "load": self.probe.load},
            "detail": self.detail,
        }


def _public_key_path(private_key_path: str) -> str:
    return private_key_path if private_key_path.endswith(".pub") else f"{private_key_path}.pub"


# authorize_fn(node, pubkey_text) -> (ok, detail). Default uses ssh to append the
# key to the remote authorized_keys idempotently.
AuthorizeFn = Callable[[Node, str], "tuple[bool, str]"]


def _default_authorize(node: Node, pubkey_text: str) -> tuple[bool, str]:
    import subprocess

    host = node.ssh_host
    if not host:
        return False, "no ssh host configured"
    target = f"{node.ssh_user}@{host}" if node.ssh_user else host
    # Idempotent append: only add the key if not already present. POSIX remote sh;
    # for a Windows OpenSSH remote the administrators_authorized_keys path differs —
    # documented in CLUSTER.md as the one platform-specific onboarding nuance.
    key = pubkey_text.strip().replace("'", "")
    remote = (
        "mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
        f"(grep -qF '{key}' ~/.ssh/authorized_keys 2>/dev/null || "
        f"echo '{key}' >> ~/.ssh/authorized_keys) && chmod 600 ~/.ssh/authorized_keys && echo AUTHORIZED"
    )
    argv = ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=10", target, remote]
    try:
        cp = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return False, f"key authorization transport failed: {type(exc).__name__}"
    ok = cp.returncode == 0 and "AUTHORIZED" in (cp.stdout or "")
    return ok, "authorized" if ok else f"authorize failed (rc={cp.returncode})"


def onboard_node(
    *,
    name: str,
    host: str,
    ssh_user: str,
    ssh_key_path: str,
    tailscale_ip: str | None = None,
    max_parallel: int = 4,
    declared: Capabilities | None = None,
    authorize: bool = True,
    authorize_fn: AuthorizeFn | None = None,
    prober: HealthProber | None = None,
) -> OnboardResult:
    """Authorize the shared key on a new node, probe it, and return the result.

    Does NOT itself persist config — the caller (CLI) writes the registry so the
    add is auditable and reversible. ``registered`` is set by the caller.
    """
    node = Node(
        name=name,
        kind="remote",
        max_parallel=max_parallel,
        hostname=host,
        tailscale_ip=tailscale_ip or host,
        ssh_user=ssh_user,
        ssh_key_path=ssh_key_path,
        capabilities=declared or Capabilities(),
    )

    key_authorized = False
    detail = ""
    if authorize:
        # Expand ~ / env vars so configs stay portable (no hardcoded user paths).
        expanded_key = os.path.expanduser(os.path.expandvars(ssh_key_path))
        pub_path = Path(_public_key_path(expanded_key))
        if not pub_path.exists():
            detail = f"public key not found at {pub_path}; skipped key authorization"
        else:
            pubkey_text = pub_path.read_text(encoding="utf-8")
            fn = authorize_fn or _default_authorize
            key_authorized, detail = fn(node, pubkey_text)

    prober = prober or HealthProber()
    probe = prober.probe(node)

    return OnboardResult(node=node, key_authorized=key_authorized, probe=probe, detail=detail)
