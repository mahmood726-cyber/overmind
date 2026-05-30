"""Unit tests for the skill promotion gate (overmind.evolution.promotion).

Fully offline. Verifies the two invariants: evidence-gated promotion (no promote
without real success evidence + thresholds) and the append-only archive
(Darwin-Gödel 'keep the archive, never silently forget').
"""
from __future__ import annotations
import json

import pytest

from overmind.evolution.skill_library import Skill, SkillLibrary
from overmind.evolution.promotion import (
    EvidenceBundle, PromotionGate, PromotionPolicy, SkillArchive,
)


def mk_skill(sid="s1", used=0, succeeded=0, durability=1.0) -> Skill:
    sk = Skill(skill_id=sid, failure_type="DEP", pattern="p",
               description="d", fix_script="pip install x")
    sk.times_used = used
    sk.times_succeeded = succeeded
    sk.durability = durability
    return sk


def lib(tmp_path, *skills) -> SkillLibrary:
    library = SkillLibrary(tmp_path / "SKILLS.json")
    for s in skills:
        library.skills[s.skill_id] = s
    return library


def gate(library, archive=None, **policy):
    return PromotionGate(library, PromotionPolicy(**policy) if policy else None,
                         archive, clock=lambda: 123.0)


# --------------------------- evaluate (pure decision) --------------------- #
def test_evaluate_hold_insufficient_uses(tmp_path):
    g = gate(lib(tmp_path), min_uses=5)
    b = g.evaluate(mk_skill(used=2, succeeded=2))
    assert b.decision == "hold" and "uses" in b.reason


def test_evaluate_hold_no_success_evidence(tmp_path):
    g = gate(lib(tmp_path), min_uses=5)
    b = g.evaluate(mk_skill(used=10, succeeded=0))
    assert b.decision == "hold" and "no successful" in b.reason


def test_evaluate_reject_low_success_rate(tmp_path):
    g = gate(lib(tmp_path), min_uses=5, min_success_rate=0.8)
    b = g.evaluate(mk_skill(used=10, succeeded=5))   # 0.5
    assert b.decision == "reject" and "success_rate" in b.reason


def test_evaluate_reject_low_durability(tmp_path):
    g = gate(lib(tmp_path), min_uses=5, min_success_rate=0.8, min_durability=0.7)
    b = g.evaluate(mk_skill(used=10, succeeded=10, durability=0.5))
    assert b.decision == "reject" and "durability" in b.reason


def test_evaluate_promote(tmp_path):
    g = gate(lib(tmp_path), min_uses=5, min_success_rate=0.8, min_durability=0.7)
    b = g.evaluate(mk_skill(used=10, succeeded=9, durability=1.0))
    assert b.decision == "promote"
    assert b.times_succeeded == 9 and b.success_rate == 0.9


# --------------------------- maybe_promote (side effects) ----------------- #
def test_maybe_promote_marks_trusted_and_archives(tmp_path):
    s = mk_skill(used=10, succeeded=9)
    library = lib(tmp_path, s)
    arch = SkillArchive(tmp_path / "archive.jsonl")
    b = gate(library, arch).maybe_promote("s1")
    assert b.decision == "promote"
    assert library.skills["s1"].trusted is True
    assert library.skills["s1"].promoted_ts == 123.0
    assert len(arch.history("s1")) == 1


def test_maybe_promote_hold_does_not_trust_but_archives(tmp_path):
    s = mk_skill(used=1, succeeded=1)
    library = lib(tmp_path, s)
    arch = SkillArchive(tmp_path / "archive.jsonl")
    b = gate(library, arch).maybe_promote("s1")
    assert b.decision == "hold"
    assert library.skills["s1"].trusted is False
    assert len(arch.all()) == 1


def test_maybe_promote_unknown_skill_fails_closed(tmp_path):
    arch = SkillArchive(tmp_path / "archive.jsonl")
    b = gate(lib(tmp_path), arch).maybe_promote("ghost")
    assert b.decision == "reject"
    assert len(arch.all()) == 1


def test_sweep_evaluates_all(tmp_path):
    library = lib(tmp_path, mk_skill("a", used=10, succeeded=9),
                 mk_skill("b", used=1, succeeded=0))
    bundles = gate(library, SkillArchive(tmp_path / "a.jsonl")).sweep()
    assert {x.skill_id for x in bundles} == {"a", "b"}
    assert library.skills["a"].trusted and not library.skills["b"].trusted


# --------------------------- SkillArchive (append-only) ------------------- #
def test_archive_append_only_and_history(tmp_path):
    arch = SkillArchive(tmp_path / "a.jsonl")
    arch.record(EvidenceBundle("x", "promote", "r", 5, 5, 1.0, 1.0))
    arch.record(EvidenceBundle("y", "hold", "r", 1, 0, 0.0, 1.0))
    assert len(arch.all()) == 2
    assert [b["skill_id"] for b in arch.history("x")] == ["x"]


def test_archive_accepts_plain_dict(tmp_path):
    arch = SkillArchive(tmp_path / "a.jsonl")
    arch.record({"skill_id": "z", "decision": "demote"})
    assert arch.all()[0]["skill_id"] == "z"


# --------------------------- demote_stale archives before delete ---------- #
def test_demote_stale_archives_before_delete(tmp_path):
    s = mk_skill(used=10, succeeded=1)   # failure rate 0.9 > 0.7
    library = lib(tmp_path, s)
    arch = SkillArchive(tmp_path / "a.jsonl")
    n = library.demote_stale(min_uses=5, max_failure_rate=0.7, archive=arch)
    assert n == 1
    assert "s1" not in library.skills          # removed from live library
    hist = arch.history("s1")                   # but preserved in the archive
    assert len(hist) == 1 and hist[0]["decision"] == "demote"


def test_demote_stale_without_archive_still_works(tmp_path):
    s = mk_skill(used=10, succeeded=1)
    library = lib(tmp_path, s)
    assert library.demote_stale(min_uses=5, max_failure_rate=0.7) == 1
    assert "s1" not in library.skills


# --------------------------- Skill backward-compat ------------------------ #
def test_skill_loads_without_new_fields(tmp_path):
    old = {"skill_id": "o", "failure_type": "DEP", "pattern": "p",
           "description": "d", "fix_script": "f"}
    sk = Skill(**old)
    assert sk.trusted is False and sk.promoted_ts == 0.0
    assert sk.to_dict()["trusted"] is False


def test_skill_roundtrip_persists_trusted(tmp_path):
    library = lib(tmp_path, mk_skill(used=10, succeeded=9))
    gate(library, SkillArchive(tmp_path / "a.jsonl")).maybe_promote("s1")
    reloaded = SkillLibrary(tmp_path / "SKILLS.json")
    assert reloaded.skills["s1"].trusted is True
