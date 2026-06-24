"""Unit tests for the sandbox-requirement policy (#3b)."""
from __future__ import annotations

from overmind.verification.sandbox_policy import (
    SandboxDecision,
    TrustLevel,
    classify_trust,
    evaluate_execution,
    gate_witnesses,
)


def test_classify_trust():
    assert classify_trust() == TrustLevel.TRUSTED
    assert classify_trust(third_party=True) == TrustLevel.UNTRUSTED
    assert classify_trust(agent_generated=True) == TrustLevel.UNTRUSTED


def test_trusted_runs_on_host():
    v = evaluate_execution(TrustLevel.TRUSTED, isolation_active=False)
    assert v.decision == SandboxDecision.HOST_OK
    assert v.counts_toward_pass is True


def test_untrusted_unisolated_is_blocked_failclosed():
    v = evaluate_execution(TrustLevel.UNTRUSTED, isolation_active=False)
    assert v.decision == SandboxDecision.BLOCKED_UNISOLATED
    assert v.counts_toward_pass is False


def test_untrusted_isolated_is_permitted():
    v = evaluate_execution(TrustLevel.UNTRUSTED, isolation_active=True)
    assert v.decision == SandboxDecision.ISOLATED_OK
    assert v.counts_toward_pass is True


def test_gate_blocks_release_on_untrusted_unisolated():
    witnesses = [
        {"name": "suite", "third_party": False, "agent_generated": False},
        {"name": "dep", "third_party": True, "agent_generated": False},
    ]
    out = gate_witnesses(witnesses, isolation_active=False)
    assert out["untrusted_unisolated_violations"] == 1
    assert out["release_blocked"] is True
    # trusted one still counts
    suite = next(r for r in out["rows"] if r["name"] == "suite")
    assert suite["counts_toward_pass"] is True


def test_gate_permits_all_when_isolation_active():
    witnesses = [
        {"name": "dep", "third_party": True, "agent_generated": False},
        {"name": "patch", "third_party": False, "agent_generated": True},
    ]
    out = gate_witnesses(witnesses, isolation_active=True)
    assert out["untrusted_unisolated_violations"] == 0
    assert out["release_blocked"] is False
    assert all(r["counts_toward_pass"] for r in out["rows"])
