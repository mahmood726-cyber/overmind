"""Unit tests for cross-repo contract-impact fan-out (#3d / B1)."""
from __future__ import annotations

from overmind.verification.contract_impact import ContractImpactGraph


def _portfolio() -> ContractImpactGraph:
    g = ContractImpactGraph()
    g.add_repo("D")
    g.add_dependency("A", depends_on="M")
    g.add_dependency("C", depends_on="M")
    g.add_dependency("B", depends_on="A")
    return g


def test_graph_selects_transitive_dependents():
    g = _portfolio()
    impacted = set(g.impacted_by("M").impacted_repos)
    assert impacted == {"A", "B", "C"}     # B is transitive via A


def test_naive_misses_transitive():
    g = _portfolio()
    assert set(g.naive_impacted_by("M")) == {"A", "C"}   # misses B


def test_independent_repo_not_impacted():
    g = _portfolio()
    assert "D" not in g.impacted_by("M").impacted_repos


def test_unknown_changed_reported():
    g = _portfolio()
    res = g.impacted_by("does_not_exist")
    assert res.unknown_changed == ["does_not_exist"]
    assert res.impacted_repos == []


def test_changed_repo_itself_included():
    # If a repo (not just a shared module) changes, it is in its own impact set.
    g = ContractImpactGraph()
    g.add_dependency("B", depends_on="A")   # A is also a repo here
    g.add_repo("A")
    res = g.impacted_by("A")
    assert "A" in res.impacted_repos and "B" in res.impacted_repos


def test_module_with_no_dependents_impacts_nothing():
    g = _portfolio()
    res = g.impacted_by("unused_module")
    # unused_module isn't in the graph -> unknown, nothing impacted
    assert res.impacted_repos == []
