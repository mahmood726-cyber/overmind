"""Filesystem routing guard (reliability — item 5).

The daily-methods-paper and journal-lane failures were the same bug: a task that
needs local data on ``F:``/``E:`` was dispatched to the Cowork sandbox (which
cannot reach those drives), so it failed or silently produced nothing. This
encodes the rule:

    Any task that needs F:/E: MUST be dispatched to an F:-capable node as a CODE
    task — never to the Cowork sandbox.

Pure functions + a guard that fails closed, so a router can call it before
dispatch. Importing this module changes nothing on its own.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Drives that live only on the local workstation fleet (not reachable from the
# Cowork sandbox).
LOCAL_FS_DRIVES = frozenset({"E", "F"})

_DRIVE_REF = re.compile(r"\b([A-Za-z]):[\\/]")


class RoutingViolation(RuntimeError):
    """Raised when a task needing local FS is routed somewhere it cannot run."""


def local_fs_drives_referenced(text: str) -> set[str]:
    """The set of local-fs drive letters (E/F) referenced in ``text`` (a command,
    path, or task description)."""
    found = {m.group(1).upper() for m in _DRIVE_REF.finditer(text or "")}
    return found & LOCAL_FS_DRIVES


def requires_local_fs(text: str) -> bool:
    return bool(local_fs_drives_referenced(text))


@dataclass(slots=True)
class RoutingDecision:
    requires_local_fs: bool
    ok: bool
    needs_drives: list[str]
    violation: str | None = None

    def to_dict(self) -> dict:
        return {
            "requires_local_fs": self.requires_local_fs,
            "ok": self.ok,
            "needs_drives": list(self.needs_drives),
            "violation": self.violation,
        }


def check_fs_routing(
    task_text: str,
    *,
    node_name: str = "",
    node_fs_drives: "list[str] | tuple[str, ...] | set[str]" = (),
    is_code_task: bool = True,
    is_sandbox: bool = False,
) -> RoutingDecision:
    """Decide whether ``task_text`` may run on the proposed target.

    A task with no F:/E: reference is always OK. Otherwise it must go to a
    non-sandbox, F:-capable node, as a CODE task.
    """
    needs = sorted(local_fs_drives_referenced(task_text))
    if not needs:
        return RoutingDecision(requires_local_fs=False, ok=True, needs_drives=[])

    if is_sandbox:
        return RoutingDecision(
            requires_local_fs=True, ok=False, needs_drives=needs,
            violation=(
                f"task needs {needs} but was routed to the Cowork sandbox "
                f"(cannot reach local drives); route to an F:-node CODE task"
            ),
        )
    if not is_code_task:
        return RoutingDecision(
            requires_local_fs=True, ok=False, needs_drives=needs,
            violation=f"task needs {needs}; must be dispatched as a CODE task, not a chat/sandbox lane",
        )
    available = {d.upper().rstrip(":") for d in node_fs_drives}
    missing = [d for d in needs if d not in available]
    if missing:
        return RoutingDecision(
            requires_local_fs=True, ok=False, needs_drives=needs,
            violation=f"node {node_name or '<unknown>'} cannot reach required drive(s) {missing}",
        )
    return RoutingDecision(requires_local_fs=True, ok=True, needs_drives=needs)


def assert_fs_routing(
    task_text: str,
    *,
    node_name: str = "",
    node_fs_drives: "list[str] | tuple[str, ...] | set[str]" = (),
    is_code_task: bool = True,
    is_sandbox: bool = False,
) -> RoutingDecision:
    """Fail-closed variant: raise ``RoutingViolation`` on a bad route."""
    decision = check_fs_routing(
        task_text, node_name=node_name, node_fs_drives=node_fs_drives,
        is_code_task=is_code_task, is_sandbox=is_sandbox,
    )
    if not decision.ok:
        raise RoutingViolation(decision.violation)
    return decision
