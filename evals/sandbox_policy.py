"""Eval 9 — sandbox-requirement policy for untrusted witness execution.

Measures the safety gap closed by ``overmind.verification.sandbox_policy``: can
**untrusted** (third-party / agent-generated) witness code run un-isolated on the
host and still count toward a release pass?

  before (no policy)  →  whenever isolation is unavailable, untrusted code runs
                          on the host and is counted — leak.
  after  (policy)      →  untrusted-on-host is BLOCKED (fail-closed); it cannot
                          count toward a release pass.

Headline — **untrusted-un-isolated-counts-as-pass rate** over the untrusted
witnesses when isolation is NOT active:

  before  100 %   →   after  0 %

with **trusted witnesses unaffected** (still run on host — no regression).

Honest scope: this is POLICY enforcement, not a microVM. It guarantees untrusted
code cannot silently become a CERTIFIED pass while un-isolated; it does not itself
provide isolation (that remains ContainerIsolation + worktree fallback).
"""
from __future__ import annotations

from overmind.verification.sandbox_policy import (
    SandboxDecision,
    classify_trust,
    evaluate_execution,
    gate_witnesses,
)

from evals.common import pct, write_result

# A batch of witnesses: trusted + untrusted (third-party / agent-generated).
_WITNESSES = [
    {"name": "test_suite", "third_party": False, "agent_generated": False},
    {"name": "smoke", "third_party": False, "agent_generated": False},
    {"name": "thirdparty_dep_tests", "third_party": True, "agent_generated": False},
    {"name": "agent_generated_patch", "third_party": False, "agent_generated": True},
]


def _baseline_counts(witnesses, *, isolation_active: bool) -> int:
    """Pre-policy behavior: every witness that ran is counted toward the pass,
    regardless of trust or isolation (the un-gated status quo)."""
    return len(witnesses)


def evaluate() -> dict:
    untrusted = [w for w in _WITNESSES if w["third_party"] or w["agent_generated"]]
    trusted = [w for w in _WITNESSES if not (w["third_party"] or w["agent_generated"])]

    # Scenario: isolation NOT active (the risky case the gate must catch).
    gated = gate_witnesses(_WITNESSES, isolation_active=False)
    by_name = {r["name"]: r for r in gated["rows"]}

    # before: every untrusted witness would have counted toward the pass.
    untrusted_counts_before = len(untrusted)
    # after: untrusted witnesses that still count toward the pass (should be 0).
    untrusted_counts_after = sum(
        1 for w in untrusted if by_name[w["name"]]["counts_toward_pass"]
    )

    # no-regression: trusted witnesses still count (run on host).
    trusted_still_count = sum(
        1 for w in trusted if by_name[w["name"]]["counts_toward_pass"]
    )

    # When isolation IS active, untrusted code is permitted (isolated_ok).
    gated_isolated = gate_witnesses(_WITNESSES, isolation_active=True)
    iso_by_name = {r["name"]: r for r in gated_isolated["rows"]}
    untrusted_permitted_when_isolated = sum(
        1 for w in untrusted if iso_by_name[w["name"]]["counts_toward_pass"]
    )

    payload = {
        "eval": "sandbox_policy",
        "n_witnesses": len(_WITNESSES),
        "n_untrusted": len(untrusted),
        "n_trusted": len(trusted),
        "untrusted_unisolated_counts_as_pass_rate_before": pct(untrusted_counts_before, len(untrusted)),
        "untrusted_unisolated_counts_as_pass_rate_after": pct(untrusted_counts_after, len(untrusted)),
        "trusted_unaffected": trusted_still_count == len(trusted),
        "release_blocked_when_untrusted_unisolated": gated["release_blocked"],
        "untrusted_permitted_when_isolation_active": untrusted_permitted_when_isolated == len(untrusted),
        "decisions_no_isolation": gated["rows"],
    }
    return payload


def main() -> dict:
    payload = evaluate()
    path = write_result("sandbox_policy", payload)
    print(f"[sandbox_policy] untrusted-un-isolated counts-as-pass rate: "
          f"{payload['untrusted_unisolated_counts_as_pass_rate_before']:.0%} (before) -> "
          f"{payload['untrusted_unisolated_counts_as_pass_rate_after']:.0%} (after)")
    print(f"[sandbox_policy] trusted witnesses unaffected: {payload['trusted_unaffected']}; "
          f"release_blocked when untrusted+unisolated: {payload['release_blocked_when_untrusted_unisolated']}")
    print(f"[sandbox_policy] untrusted permitted when isolation active: "
          f"{payload['untrusted_permitted_when_isolation_active']}")
    print(f"[sandbox_policy] -> {path}")
    return payload


if __name__ == "__main__":
    main()
