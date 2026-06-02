"""Tests for EvolutionManager.list_recipes() (P3-e CLI exposure)."""
from __future__ import annotations

from types import SimpleNamespace

from overmind.evolution.manager import EvolutionManager


def _diag(project_id, failure_type, evidence, action):
    return SimpleNamespace(project_id=project_id, failure_type=failure_type,
                           evidence=evidence, recommended_action=action)


def test_empty_library(tmp_path):
    r = EvolutionManager(tmp_path).list_recipes()
    assert r["total"] == 0
    assert r["proven"] == 0
    assert r["recipes"] == []


def test_lists_recipe_after_evolve(tmp_path):
    mgr = EvolutionManager(tmp_path)
    diag = _diag("proj-x", "DEPENDENCY_ROT",
                 ["No module named 'cryptography'"], "pip install cryptography")
    mgr.evolve([diag])
    listing = mgr.list_recipes()
    assert listing["total"] >= 1
    rec = listing["recipes"][0]
    assert rec["failure_type"] == "DEPENDENCY_ROT"
    assert "recipe_id" in rec and "durability" in rec and "proven" in rec
