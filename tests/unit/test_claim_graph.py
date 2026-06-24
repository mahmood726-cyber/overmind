"""Unit tests for the claim->evidence dependency graph (audit B2)."""
from __future__ import annotations

import pytest

from overmind.verification.claim_graph import ClaimGraph, RetractionResult


def _chain() -> ClaimGraph:
    # evidence_A <- claim_B <- claim_C  (C depends on B depends on A); D independent.
    g = ClaimGraph()
    g.add_dependency("claim_B", depends_on="evidence_A")
    g.add_dependency("claim_C", depends_on="claim_B")
    g.add_node("claim_D")
    return g


def test_retract_propagates_transitively():
    g = _chain()
    res = g.retract("evidence_A")
    assert res.retracted == ["evidence_A"]
    # both downstream claims invalidated, deterministic order (B before C)
    assert res.invalidated == ["claim_B", "claim_C"]
    assert "claim_D" not in res.all_affected


def test_retract_does_not_over_propagate():
    g = _chain()
    # retracting a leaf claim invalidates nothing downstream
    res = g.retract("claim_C")
    assert res.retracted == ["claim_C"]
    assert res.invalidated == []


def test_retract_unknown_seed_reported():
    g = _chain()
    res = g.retract("not_a_node")
    assert res.unknown_seeds == ["not_a_node"]
    assert res.retracted == []
    assert res.invalidated == []


def test_retract_middle_node_propagates_up_only():
    g = _chain()
    res = g.retract("claim_B")
    assert res.retracted == ["claim_B"]
    assert res.invalidated == ["claim_C"]      # C depended on B
    # evidence_A is a premise of B, not a dependent -> untouched
    assert "evidence_A" not in res.all_affected


def test_cycle_is_safe():
    g = ClaimGraph()
    g.add_dependency("a", depends_on="b")
    g.add_dependency("b", depends_on="c")
    # introduce a cycle c depends on a
    g.add_dependency("c", depends_on="a")
    res = g.retract("a")
    # all reachable, no infinite loop, each node once
    assert set(res.all_affected) == {"a", "b", "c"}


def test_self_dependency_rejected():
    g = ClaimGraph()
    with pytest.raises(ValueError):
        g.add_dependency("x", depends_on="x")


def test_diamond_dependency_dedups():
    # A <- B, A <- C, B <- D, C <- D : retracting A hits B,C,D once each.
    g = ClaimGraph()
    g.add_dependency("B", depends_on="A")
    g.add_dependency("C", depends_on="A")
    g.add_dependency("D", depends_on="B")
    g.add_dependency("D", depends_on="C")
    res = g.retract("A")
    assert res.retracted == ["A"]
    assert sorted(res.invalidated) == ["B", "C", "D"]
    assert res.invalidated.count("D") == 1


def test_multi_seed_retraction():
    g = _chain()
    res = g.retract("evidence_A", "claim_D")
    assert set(res.retracted) == {"evidence_A", "claim_D"}
    assert res.invalidated == ["claim_B", "claim_C"]
