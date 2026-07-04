"""Tests for the AN-7 in-house adversarial corpus audit."""
from __future__ import annotations

from overmind.benchmark.benchjack_audit import (
    audit_corpus,
    exploits_to_fixtures,
)
from overmind.benchmark.generate import generate


def test_audit_runs_on_real_corpus():
    tasks, keys = generate(max_fixtures=4)
    kd = {k.id: k for k in keys}
    report = audit_corpus(tasks, kd)
    assert report.n_tasks == len(tasks)
    # our corpus has a canary (witness-detectable defects) -> no 'no_canary' exploit
    assert not any(e.name == "no_canary" for e in report.exploits)


def test_audit_flags_id_encodes_label():
    tasks, keys = generate(max_fixtures=3)
    kd = {k.id: k for k in keys}
    report = audit_corpus(tasks, kd)
    assert any(e.name == "id_encodes_label" for e in report.exploits)


def test_audit_does_not_flag_id_in_prompt():
    # blinding holds: the id must NOT reach the reviewer prompt
    tasks, keys = generate(max_fixtures=3)
    kd = {k.id: k for k in keys}
    report = audit_corpus(tasks, kd)
    assert not any(e.name == "id_in_prompt" for e in report.exploits)


def test_audit_finds_keyword_shortcuts():
    # the templated reviewer-only classes are pattern-matchable -> audit surfaces it
    tasks, keys = generate(max_fixtures=5)
    kd = {k.id: k for k in keys}
    report = audit_corpus(tasks, kd)
    assert any(e.name.startswith("keyword_shortcut:") for e in report.exploits)


def test_exploits_become_negative_memory_fixtures():
    tasks, keys = generate(max_fixtures=4)
    kd = {k.id: k for k in keys}
    report = audit_corpus(tasks, kd)
    fixtures = exploits_to_fixtures(report)
    assert fixtures and all(f["type"] == "negative_memory" for f in fixtures)
    assert all("guard" in f for f in fixtures)


def test_audit_flags_missing_canary():
    from overmind.benchmark.tasks import AnswerKey, Task, DIRECTION
    # a corpus with ONLY reviewer-only defects and no witness-detectable canary
    tasks = [Task("x__direction", DIRECTION, "artifact", data={})]
    keys = {"x__direction": AnswerKey("x__direction", True, "wrong_direction")}
    report = audit_corpus(tasks, keys)
    assert any(e.name == "no_canary" for e in report.exploits)
