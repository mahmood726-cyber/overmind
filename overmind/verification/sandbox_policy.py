"""Sandbox-requirement policy for witness execution (audit / sandboxing gap).

Today witness code (test suites, smoke imports, numerical runs) executes as host
subprocesses. For a portfolio of *self-authored* repos the blast radius is low,
so that is acceptable — but the moment a witness runs **third-party or
agent-generated** code on the host, an un-isolated execution should NOT be able
to produce a release pass. The frontier answer is microVM/gVisor isolation
(Inspect Sandboxing Toolkit, E2B/Modal/Daytona). Full microVM execution is
multi-session infra and depends on a runtime that may be absent on a given host.

What this module adds NOW (machine-independent, fail-closed): a deterministic
**policy gate** that classifies each witness by trust level and decides whether
its execution is permitted to count toward a verdict:

  * trusted (self-authored)         → may run on host.
  * untrusted (3rd-party / agent)   → MUST run isolated; if isolation is
                                       unavailable/disabled, the execution is
                                       BLOCKED (fail-closed) — it cannot be a
                                       release pass.

This is honest about its scope: it is **policy enforcement**, not a microVM. It
guarantees untrusted code never silently becomes a CERTIFIED pass while running
un-isolated; it does not itself provide the isolation (that remains
``ContainerIsolation`` + worktree fallback). Pairs with the truth-first house
rule that a missing safety precondition downgrades the verdict, never relaxes it.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TrustLevel(str, Enum):
    TRUSTED = "trusted"        # self-authored portfolio code
    UNTRUSTED = "untrusted"    # third-party or agent-generated code


class SandboxDecision(str, Enum):
    HOST_OK = "host_ok"                 # trusted: host execution permitted
    ISOLATED_OK = "isolated_ok"         # untrusted, ran isolated: permitted
    BLOCKED_UNISOLATED = "blocked_unisolated"  # untrusted, no isolation: fail-closed


@dataclass(slots=True, frozen=True)
class SandboxVerdict:
    decision: SandboxDecision
    counts_toward_pass: bool   # may this witness contribute to a release pass?
    reason: str


def classify_trust(*, third_party: bool = False, agent_generated: bool = False) -> TrustLevel:
    """A witness is UNTRUSTED if it runs third-party or agent-generated code."""
    return TrustLevel.UNTRUSTED if (third_party or agent_generated) else TrustLevel.TRUSTED


def evaluate_execution(
    trust: TrustLevel,
    *,
    isolation_active: bool,
) -> SandboxVerdict:
    """Decide whether a witness execution is permitted to count toward a verdict.

    ``isolation_active`` = a real isolation runtime ran this witness (e.g.
    ``ContainerIsolation.describe()['active']`` is True). Trusted code is fine on
    the host; untrusted code is permitted only when isolation actually ran, else
    it is BLOCKED (fail-closed) and must not contribute to a release pass.
    """
    if trust == TrustLevel.TRUSTED:
        return SandboxVerdict(
            SandboxDecision.HOST_OK, True,
            "trusted (self-authored) code — host execution permitted",
        )
    if isolation_active:
        return SandboxVerdict(
            SandboxDecision.ISOLATED_OK, True,
            "untrusted code ran under active isolation — permitted",
        )
    return SandboxVerdict(
        SandboxDecision.BLOCKED_UNISOLATED, False,
        "untrusted (third-party/agent-generated) code ran WITHOUT isolation — "
        "blocked: cannot count toward a release pass (fail-closed)",
    )


def gate_witnesses(witnesses: list[dict], *, isolation_active: bool) -> dict:
    """Apply the policy to a batch of witness descriptors.

    Each ``witnesses`` item: ``{"name": str, "third_party": bool,
    "agent_generated": bool}``. Returns a summary with the per-witness decisions
    and whether any untrusted witness ran un-isolated (a release-blocking
    violation).
    """
    rows = []
    violations = 0
    for w in witnesses:
        trust = classify_trust(
            third_party=w.get("third_party", False),
            agent_generated=w.get("agent_generated", False),
        )
        verdict = evaluate_execution(trust, isolation_active=isolation_active)
        if verdict.decision == SandboxDecision.BLOCKED_UNISOLATED:
            violations += 1
        rows.append({
            "name": w.get("name"),
            "trust": trust.value,
            "decision": verdict.decision.value,
            "counts_toward_pass": verdict.counts_toward_pass,
        })
    return {
        "isolation_active": isolation_active,
        "rows": rows,
        "untrusted_unisolated_violations": violations,
        "release_blocked": violations > 0,
    }
