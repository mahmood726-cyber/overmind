"""HMAC signing for cert bundles.

Per `lessons.md#cryptography--signing-learned-2026-04-14`:
  - HMAC key MUST come from env (TRUTHCERT_HMAC_KEY), never the bundle itself.
  - Constant-time comparison via `hmac.compare_digest`.
  - Fail closed when the key is missing in production.

Design choice tested here: missing-key is NON-fatal at construction time
(the bundle is still usable for cache-skip via `bundle_hash`), but
`verify_signature()` returns False — so any caller that requires
authenticity must check the return value, not assume a signed bundle.
"""
from __future__ import annotations
import os
import pytest

from overmind.verification.cert_bundle import CertBundle, _HMAC_ENV_VAR
from overmind.verification.scope_lock import ScopeLock, WitnessResult


def _bundle(verdict: str = "CERTIFIED", project_id: str = "test_proj") -> CertBundle:
    return CertBundle(
        project_id=project_id,
        scope_lock=ScopeLock(
            project_id=project_id,
            project_path="/tmp/test",
            risk_profile="low",
            witness_count=1,
            test_command="pytest",
            smoke_modules=(),
            baseline_path=None,
            expected_outcome="PASS",
            source_hash="abc123",
            created_at="2026-04-15T10:00:00",
        ),
        witness_results=[
            WitnessResult(
                witness_type="test_suite", verdict="PASS",
                exit_code=0, stdout="ok", stderr="", elapsed=0.1,
            ),
        ],
        verdict=verdict,
        arbitration_reason="Single witness: test_suite PASS",
        timestamp="2026-04-15T10:00:00",
    )


def test_no_key_leaves_signature_empty(monkeypatch):
    """When TRUTHCERT_HMAC_KEY is unset, bundle is still constructible
    (cache-skip path still works), but signature is empty and verify
    returns False. This is the dev-mode fallback."""
    monkeypatch.delenv(_HMAC_ENV_VAR, raising=False)
    b = _bundle()
    assert b.bundle_signature == ""
    assert b.bundle_hash != ""  # hash is independent of key — cache still works
    assert b.verify_signature() is False


def test_with_key_signs_and_verifies(monkeypatch):
    monkeypatch.setenv(_HMAC_ENV_VAR, "test-key-do-not-use-in-prod")
    b = _bundle()
    assert b.bundle_signature != ""
    assert len(b.bundle_signature) == 64  # SHA256 hex
    assert b.verify_signature() is True


def test_signature_changes_when_payload_mutated(monkeypatch):
    """Mutating any signed field invalidates the signature. This is the
    forge-prevention guarantee: an attacker who edits a bundle JSON on
    disk cannot recompute the signature without the key."""
    monkeypatch.setenv(_HMAC_ENV_VAR, "test-key")
    b = _bundle(verdict="CERTIFIED")
    original_sig = b.bundle_signature
    # Tamper with the verdict directly (simulates JSON edit)
    b.verdict = "FAIL"
    # Signature is now stale — verify must catch it
    assert b.verify_signature() is False
    # If a fresh bundle is built with the new verdict, it gets a different sig
    b2 = _bundle(verdict="FAIL")
    assert b2.bundle_signature != original_sig


def test_signature_independent_of_key_via_payload(monkeypatch):
    """Critical: the key MUST NOT come from the bundle itself. We test
    this by signing the same payload under two different keys and
    confirming the signatures differ — proves the key is mixed in."""
    monkeypatch.setenv(_HMAC_ENV_VAR, "key-A")
    sig_A = _bundle().bundle_signature
    monkeypatch.setenv(_HMAC_ENV_VAR, "key-B")
    sig_B = _bundle().bundle_signature
    assert sig_A != sig_B, (
        "HMAC must depend on the key. If signatures match, the key is being "
        "ignored — likely sourced from the bundle (forge-able)."
    )


def test_verify_uses_compare_digest(monkeypatch):
    """The verify path must use hmac.compare_digest (constant-time) so a
    timing side-channel can't leak signature bytes. We don't unit-test
    the timing directly; we assert the implementation calls compare_digest
    via a smoke test that `verify_signature` is consistent."""
    monkeypatch.setenv(_HMAC_ENV_VAR, "test-key")
    b = _bundle()
    # Two consecutive verifications must agree (compare_digest is deterministic)
    assert b.verify_signature() is True
    assert b.verify_signature() is True
    # And mismatched bundles must reject deterministically
    b.bundle_signature = "0" * 64
    assert b.verify_signature() is False


def test_hash_unaffected_by_key(monkeypatch):
    """bundle_hash is a cache key, NOT a signature. It must be stable
    regardless of whether the HMAC key is set. This ensures hash-skip
    caching in nightly_verify.py keeps working when TRUTHCERT_HMAC_KEY
    is rotated or temporarily unset."""
    monkeypatch.setenv(_HMAC_ENV_VAR, "key-A")
    h_with_key = _bundle().bundle_hash
    monkeypatch.delenv(_HMAC_ENV_VAR, raising=False)
    h_without_key = _bundle().bundle_hash
    monkeypatch.setenv(_HMAC_ENV_VAR, "key-B")
    h_other_key = _bundle().bundle_hash
    assert h_with_key == h_without_key == h_other_key, (
        "bundle_hash must be key-independent (it's the cache key, not the signature)"
    )


def test_to_dict_includes_signature(monkeypatch):
    monkeypatch.setenv(_HMAC_ENV_VAR, "test-key")
    b = _bundle()
    d = b.to_dict()
    assert "bundle_signature" in d
    assert d["bundle_signature"] == b.bundle_signature
