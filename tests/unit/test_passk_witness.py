"""Tests for the AN-5 passk + signature-determinism witnesses (passk_witness)."""
from __future__ import annotations

from overmind.verification.passk_witness import (
    pass_at_k,
    passk,
    signature_determinism,
    signature_of,
    verified_promotion,
)


def test_passk_requires_all():
    assert passk([True, True, True]) is True
    assert passk([True, False, True]) is False
    assert passk([]) is False


def test_pass_at_k_is_weaker():
    assert pass_at_k([False, False, True]) is True
    assert passk([False, False, True]) is False   # passk stricter


def test_signature_stable_for_identical_calls():
    calls = [{"name": "pool", "args": {"measure": "RR"}}]
    assert signature_of(calls) == signature_of(calls)


def test_signature_determinism_all_identical():
    calls = [{"name": "pool", "args": {"m": "RR"}}]
    r = signature_determinism([calls, calls, calls])
    assert r.deterministic is True
    assert r.distinct_signatures == 1
    assert r.n_replays == 3


def test_signature_determinism_detects_drift():
    a = [{"name": "pool", "args": {"m": "RR"}}]
    b = [{"name": "pool", "args": {"m": "OR"}}]   # different args
    r = signature_determinism([a, a, b])
    assert r.deterministic is False
    assert r.distinct_signatures == 2


def test_verified_promotion_passk_only():
    p = verified_promotion([True, True, True])
    assert p.promote is True and p.passk_ok is True


def test_verified_promotion_blocks_on_failed_replay():
    p = verified_promotion([True, False, True])
    assert p.promote is False and "not passk" in p.note


def test_verified_promotion_signature_required():
    a = [{"name": "t", "args": {}}]
    b = [{"name": "t", "args": {"x": 1}}]
    # passk holds but signatures drift -> not verified when signature required
    p = verified_promotion([True, True], [a, b], require_signature=True)
    assert p.promote is False and "drifts" in p.note


def test_verified_promotion_signature_deterministic():
    a = [{"name": "t", "args": {}}]
    p = verified_promotion([True, True], [a, a], require_signature=True)
    assert p.promote is True
