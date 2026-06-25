"""SSH transport for remote verification jobs (real, key-auth, safe-by-default).

This is the real remote-execution path that the benchmark flagged as a
``NotImplementedError`` stub. A remote job carries a ``command`` (an allowlisted
verification command — ``python -m ...`` / ``pytest`` / a repo-local script); the
``SSHExecutor`` runs it on the node over key-auth SSH, captures stdout, and parses
a JSON result line.

Safety (the standing constraints, enforced here, not assumed):

  * **No force-push.** ``assert_command_safe`` refuses any ``git push --force`` /
    ``-f`` / ``+<refspec>`` before a command can leave this machine.
  * **No Sentinel bypass.** ``SENTINEL_BYPASS`` / ``--no-verify`` / ``--no-gpg-sign``
    are refused, so a dispatched job inherits the remote repo's pre-push gating.
  * **No secret leakage.** Only the key *path* is passed (``ssh -i <path>``); key
    material is never read or logged. Errors are classified, never dumped with env.
  * **Transient-vs-real.** Connection failures (ssh exit 255, refused, timeout,
    unreachable) are marked ``transient`` so the scheduler can requeue to another
    node rather than recording a false verification failure.

The actual ``subprocess`` call is injectable (``transport=`` / ``run_fn=``) so the
scheduler, health prober, and evals are fully testable offline.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from typing import Callable

from overmind.cluster.registry import Executor, Node

# Tokens that must never appear in a dispatched command — each encodes a standing
# constraint (force-push off / Sentinel-gating inherited / signing not bypassed).
_FORCE_PUSH_RE = re.compile(r"\bpush\b.*(--force\b|--force-with-lease\b|(?<!\w)-f(?!\w)|\s\+\S)", re.IGNORECASE)
_BYPASS_TOKENS = ("sentinel_bypass", "--no-verify", "--no-gpg-sign", "-c core.hookspath")


class UnsafeCommandError(ValueError):
    """Raised when a job command would violate a standing safety constraint."""


def assert_command_safe(command: str) -> None:
    """Fail closed if ``command`` would force-push, bypass Sentinel, or skip signing."""
    if not command or not command.strip():
        raise UnsafeCommandError("empty command")
    lowered = command.lower()
    if _FORCE_PUSH_RE.search(command):
        raise UnsafeCommandError("force-push is disabled for dispatched jobs")
    for tok in _BYPASS_TOKENS:
        if tok in lowered:
            raise UnsafeCommandError(f"dispatched job may not use {tok!r} (Sentinel gating is inherited)")


@dataclass(slots=True)
class TransportResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""
    transient: bool = False   # connection-level failure → safe to requeue elsewhere

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.transient


# ssh exit 255 == ssh itself failed to connect (vs the remote command's own code).
_TRANSIENT_PATTERNS = (
    "connection refused", "connection timed out", "connection closed",
    "no route to host", "host is down", "network is unreachable",
    "operation timed out", "timed out", "could not resolve hostname",
    "permission denied (publickey", "broken pipe", "kex_exchange",
)


def _looks_transient(returncode: int, stderr: str) -> bool:
    if returncode == 255:
        return True
    low = (stderr or "").lower()
    return any(p in low for p in _TRANSIENT_PATTERNS)


def build_ssh_argv(
    node: Node,
    remote_command: str,
    *,
    connect_timeout: int = 8,
) -> list[str]:
    """Build the ``ssh`` argv to run ``remote_command`` on ``node`` over key auth.

    Key auth only (``BatchMode=yes`` → never prompt for a password); the private
    key is referenced by *path*, never read here.
    """
    host = node.ssh_host
    if not host:
        raise UnsafeCommandError(f"node {node.name!r} has no ssh host (tailscale_ip/hostname)")
    assert_command_safe(remote_command)
    target = f"{node.ssh_user}@{host}" if node.ssh_user else host
    argv = ["ssh"]
    if node.ssh_key_path:
        # Expand ~ / env vars so configs stay portable (no hardcoded user paths).
        argv += ["-i", os.path.expanduser(os.path.expandvars(node.ssh_key_path))]
    argv += [
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", f"ConnectTimeout={connect_timeout}",
        target,
        remote_command,
    ]
    return argv


# A run_fn takes argv + timeout and returns (returncode, stdout, stderr).
RunFn = Callable[[list[str], float], "subprocess.CompletedProcess | tuple[int, str, str]"]


def _default_run_fn(argv: list[str], timeout: float) -> tuple[int, str, str]:
    try:
        cp = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return cp.returncode, cp.stdout or "", cp.stderr or ""
    except subprocess.TimeoutExpired:
        return 255, "", "operation timed out"
    except FileNotFoundError:
        # ssh binary missing on this host — a real, non-transient config problem.
        return 127, "", "ssh executable not found on dispatcher host"


class SSHTransport:
    """Runs a remote command over SSH using key auth. Injectable run function."""

    def __init__(self, run_fn: RunFn | None = None, *, connect_timeout: int = 8) -> None:
        self._run_fn = run_fn or _default_run_fn
        self._connect_timeout = connect_timeout

    def run(self, node: Node, remote_command: str, *, timeout: float = 900.0) -> TransportResult:
        argv = build_ssh_argv(node, remote_command, connect_timeout=self._connect_timeout)
        raw = self._run_fn(argv, timeout)
        if isinstance(raw, subprocess.CompletedProcess):
            rc, out, err = raw.returncode, raw.stdout or "", raw.stderr or ""
        else:
            rc, out, err = raw
        return TransportResult(
            returncode=rc,
            stdout=out,
            stderr=err,
            transient=_looks_transient(rc, err),
        )


def parse_result_line(stdout: str) -> dict | None:
    """Parse the last JSON object printed by a remote verification command.

    Remote verifiers print a final ``{"repo": ..., "verdict": ...}`` line; we read
    the last parseable JSON object so log chatter before it is ignored.
    """
    for line in reversed([ln.strip() for ln in (stdout or "").splitlines() if ln.strip()]):
        if line.startswith("{") and line.endswith("}"):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                return obj
    return None


class SSHExecutor:
    """Real remote executor: runs a job's ``command`` on ``node`` over SSH.

    Replaces the previous ``RemoteExecutor`` stub. The job MUST carry a ``command``
    (the local-runner closure cannot cross the wire). A connection-level failure
    surfaces as ``RemoteTransientError`` so the scheduler requeues the job to
    another capable node instead of recording a verification failure.
    """

    def __init__(self, node: Node, transport: SSHTransport | None = None) -> None:
        self.node = node
        self._transport = transport or SSHTransport()

    @property
    def name(self) -> str:
        return f"ssh:{self.node.name}"

    def run(self, job: dict, runner: Callable[[dict], dict]) -> dict:
        command = job.get("command")
        if not command:
            raise UnsafeCommandError(
                f"remote job for repo {job.get('repo')!r} has no 'command'; remote "
                "executors run an explicit verification command, not a local closure"
            )
        assert_command_safe(command)
        timeout = float(job.get("timeout", 900.0))
        res = self._transport.run(self.node, command, timeout=timeout)
        if res.transient:
            raise RemoteTransientError(
                f"transient SSH failure to node {self.node.name!r} "
                f"(rc={res.returncode}): {(res.stderr or '').strip()[:160]}"
            )
        parsed = parse_result_line(res.stdout) or {}
        out = dict(parsed)
        out.setdefault("repo", job.get("repo"))
        # The remote command's own exit code is authoritative for pass/fail when it
        # did not print a verdict line.
        if "verdict" not in out:
            out["verdict"] = "PASS" if res.returncode == 0 else "FAIL"
        out["executor"] = self.name
        out["node"] = self.node.name
        out["returncode"] = res.returncode
        return out


class RemoteTransientError(RuntimeError):
    """A connection-level failure that means the node is (likely) offline — the
    scheduler should mark it offline and requeue the job elsewhere."""


# Backward-compatible alias. The old name implied "deferred/stub"; it is now the
# real SSH executor. Kept so existing imports keep working.
RemoteExecutor = SSHExecutor
