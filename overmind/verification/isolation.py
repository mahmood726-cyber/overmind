"""Container isolation for high-risk verification (skeleton + fallback).

Full Docker integration is multi-session work — Dockerfile templates per
stack (Python, Node, R), resource limits, network lockdown, volume mount
hardening. This module ships:

  1. A runtime detector (`is_container_runtime_available`) that reports
     whether Docker, Podman, or WSL2 is usable on this machine.
  2. A `ContainerIsolation` façade with a `run_in_container` method that
     is **wired but inactive**: when a container runtime is not
     available OR `enabled=False`, it returns a SKIP-equivalent so callers
     can fall through to the existing worktree isolation.
  3. An `isolation_mode` config hook so `policies.yaml` can set
     `isolation.container: false` (default) or `true` without other
     subsystems caring whether containers are actually running.

Landing the skeleton lets callers (TruthCertEngine, VerificationEngine)
adopt the interface now; the full Docker execution path can land without
touching their code later.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


ContainerRuntime = Literal["docker", "podman", "wsl", "none"]


@dataclass(slots=True)
class ContainerRunResult:
    verdict: Literal["RAN", "SKIP", "FAIL"]
    exit_code: int | None
    stdout: str
    stderr: str
    runtime: ContainerRuntime


def detect_container_runtime() -> ContainerRuntime:
    """Return the preferred runtime available on this host.

    Order: docker → podman → WSL2 (Windows) → none. `docker --version`
    succeeding means the CLI is present; it does NOT guarantee the daemon
    is running. Callers must still handle `ContainerRunResult.verdict == "FAIL"`.
    """
    for runtime in ("docker", "podman"):
        if shutil.which(runtime):
            try:
                proc = subprocess.run(
                    [runtime, "--version"],
                    capture_output=True, text=True, timeout=5,
                )
                if proc.returncode == 0:
                    return runtime  # type: ignore[return-value]
            except (subprocess.TimeoutExpired, OSError):
                continue
    if shutil.which("wsl"):
        try:
            proc = subprocess.run(
                ["wsl", "--status"],
                capture_output=True, text=True, timeout=5,
            )
            if proc.returncode == 0:
                return "wsl"
        except (subprocess.TimeoutExpired, OSError):
            pass
    return "none"


def is_container_runtime_available() -> bool:
    return detect_container_runtime() != "none"


class ContainerIsolation:
    """Optional containerised execution for high-risk verification.

    Current behaviour: if a runtime is detected AND `enabled=True`, the
    skeleton is wired up but intentionally returns `verdict="SKIP"` with
    stderr explaining that the full container path is not yet implemented.
    Callers should fall back to the existing worktree isolation when
    `verdict != "RAN"`. This lets us land the interface and detector now
    and fill in Dockerfile templates as a dedicated follow-up.
    """

    STUB_STDERR = (
        "container isolation skeleton only; full execution path not yet "
        "implemented. Falling back to worktree isolation. Set "
        "isolation.container=false in policies.yaml to silence this."
    )

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.runtime = detect_container_runtime() if enabled else "none"

    def run_in_container(
        self,
        command: str,
        cwd: str | Path,
        *,
        stack: str = "python",
        timeout: int = 300,
    ) -> ContainerRunResult:
        if not self.enabled:
            return ContainerRunResult(
                verdict="SKIP", exit_code=None, stdout="",
                stderr="container isolation disabled",
                runtime="none",
            )
        if self.runtime == "none":
            return ContainerRunResult(
                verdict="SKIP", exit_code=None, stdout="",
                stderr="no container runtime detected (docker/podman/wsl)",
                runtime="none",
            )
        _ = (command, cwd, stack, timeout)  # reserved for Dockerfile-template path
        return ContainerRunResult(
            verdict="SKIP", exit_code=None, stdout="",
            stderr=self.STUB_STDERR, runtime=self.runtime,
        )

    def describe(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "runtime": self.runtime,
            "active": self.enabled and self.runtime != "none",
            "implementation": "skeleton",
        }
