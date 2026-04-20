"""CertBundle integration with the pluggable signer framework.

Exercises the full signing pipeline at the CertBundle level — the HMAC
path is already covered in test_cert_bundle_hmac.py. This module covers:

  - Ed25519 end-to-end (keypair generate → sign bundle → verify bundle)
  - Legacy compat: a pre-signers bundle (HMAC hex, no signature_method)
    must still verify when TRUTHCERT_HMAC_KEY is present.
  - Method dispatch: a tampered signature_method on disk can't be used
    to fake a verify pass.
  - to_dict round-trip carries the new fields.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from overmind.verification.cert_bundle import CertBundle
from overmind.verification.scope_lock import ScopeLock, WitnessResult
from overmind.verification.signers import (
    ENV_ED25519_KEY,
    ENV_HMAC_KEY,
    ENV_METHOD,
    ENV_SIGSTORE_TOKEN,
    Ed25519Signer,
)


def _bundle(verdict: str = "CERTIFIED", project_id: str = "integ_proj") -> CertBundle:
    return CertBundle(
        project_id=project_id,
        scope_lock=ScopeLock(
            project_id=project_id,
            project_path="/tmp/integ",
            risk_profile="low",
            witness_count=1,
            test_command="pytest",
            smoke_modules=(),
            baseline_path=None,
            expected_outcome="PASS",
            source_hash="deadbeef",
            created_at="2026-04-18T10:00:00",
        ),
        witness_results=[
            WitnessResult(
                witness_type="test_suite", verdict="PASS",
                exit_code=0, stdout="ok", stderr="", elapsed=0.1,
            ),
        ],
        verdict=verdict,
        arbitration_reason="Single witness: test_suite PASS",
        timestamp="2026-04-18T10:00:00",
    )


def _clear_signer_env(monkeypatch):
    for var in (ENV_METHOD, ENV_HMAC_KEY, ENV_ED25519_KEY, ENV_SIGSTORE_TOKEN):
        monkeypatch.delenv(var, raising=False)


# --- Ed25519 end-to-end ---------------------------------------------

def test_ed25519_bundle_sign_and_verify(monkeypatch, tmp_path: Path):
    _clear_signer_env(monkeypatch)
    priv, _ = Ed25519Signer.generate_keypair(tmp_path)
    monkeypatch.setenv(ENV_ED25519_KEY, str(priv))

    b = _bundle()
    assert b.signature_method == "ed25519"
    assert b.bundle_signature != ""
    assert b.signature_public_key != ""
    assert b.verify_signature() is True


def test_ed25519_tampered_payload_fails_verify(monkeypatch, tmp_path: Path):
    _clear_signer_env(monkeypatch)
    priv, _ = Ed25519Signer.generate_keypair(tmp_path)
    monkeypatch.setenv(ENV_ED25519_KEY, str(priv))

    b = _bundle(verdict="CERTIFIED")
    assert b.verify_signature() is True
    # Simulate an on-disk edit of the verdict field
    b.verdict = "FAIL"
    assert b.verify_signature() is False


def test_ed25519_verify_does_not_need_private_key(monkeypatch, tmp_path: Path):
    """The public key travels inline in the bundle — verifying is a
    third-party-viable operation without access to the signer's private key."""
    _clear_signer_env(monkeypatch)
    priv, _ = Ed25519Signer.generate_keypair(tmp_path)
    monkeypatch.setenv(ENV_ED25519_KEY, str(priv))
    b = _bundle()
    assert b.verify_signature() is True

    # Now simulate a consumer: no private key configured at all.
    _clear_signer_env(monkeypatch)
    assert b.verify_signature() is True, (
        "ed25519 verification must NOT depend on the signer's private key being "
        "available in the verifier's env — the public key is in the bundle."
    )


# --- Precedence: explicit method overrides auto-detection -----------

def test_explicit_hmac_picks_hmac_even_when_ed25519_available(monkeypatch, tmp_path: Path):
    _clear_signer_env(monkeypatch)
    priv, _ = Ed25519Signer.generate_keypair(tmp_path)
    monkeypatch.setenv(ENV_ED25519_KEY, str(priv))
    monkeypatch.setenv(ENV_HMAC_KEY, "shared-secret")
    monkeypatch.setenv(ENV_METHOD, "hmac")

    b = _bundle()
    assert b.signature_method == "hmac"
    assert len(b.bundle_signature) == 64  # sha256 hex
    assert b.signature_public_key == ""   # hmac has no public key
    assert b.verify_signature() is True


# --- Legacy compat: bundles with no signature_method ----------------

def test_legacy_hmac_bundle_without_method_still_verifies(monkeypatch):
    """A bundle written before the signers refactor has HMAC signature but
    no signature_method recorded. verify_signature() must treat empty
    method as legacy HMAC to avoid breaking archived nightly outputs."""
    _clear_signer_env(monkeypatch)
    monkeypatch.setenv(ENV_HMAC_KEY, "legacy-key")

    b = _bundle()
    # Simulate loading a pre-refactor bundle: wipe the method field, keep sig.
    legacy_sig = b.bundle_signature
    b.signature_method = ""
    assert b.bundle_signature == legacy_sig  # untouched
    assert b.verify_signature() is True, (
        "legacy bundles (no signature_method) must fall back to HMAC to "
        "preserve verifiability of archived nightly outputs"
    )


def test_tampered_method_breaks_verify(monkeypatch, tmp_path: Path):
    """An attacker can't forge a verify-pass by swapping the method field.
    An ed25519 signature reinterpreted as HMAC will not match the HMAC hex
    digest of the same payload."""
    _clear_signer_env(monkeypatch)
    priv, _ = Ed25519Signer.generate_keypair(tmp_path)
    monkeypatch.setenv(ENV_ED25519_KEY, str(priv))
    monkeypatch.setenv(ENV_HMAC_KEY, "attacker-key")

    b = _bundle()
    assert b.signature_method == "ed25519"
    # Attacker rewrites signature_method to hmac to try to route through
    # the HMAC verifier with their own key. Must fail.
    b.signature_method = "hmac"
    assert b.verify_signature() is False


# --- Unsigned fallback ---------------------------------------------

def test_no_signer_configured_leaves_all_fields_empty(monkeypatch):
    _clear_signer_env(monkeypatch)
    b = _bundle()
    assert b.bundle_signature == ""
    assert b.signature_method == ""
    assert b.signature_public_key == ""
    assert b.verify_signature() is False
    # bundle_hash remains populated regardless — cache-skip still works
    assert b.bundle_hash != ""


# --- Serialization --------------------------------------------------

def test_to_dict_carries_signer_fields(monkeypatch, tmp_path: Path):
    _clear_signer_env(monkeypatch)
    priv, _ = Ed25519Signer.generate_keypair(tmp_path)
    monkeypatch.setenv(ENV_ED25519_KEY, str(priv))
    b = _bundle()

    d = b.to_dict()
    assert d["signature_method"] == "ed25519"
    assert d["signature_public_key"] == b.signature_public_key
    assert d["bundle_signature"] == b.bundle_signature


def test_roundtrip_through_dict_preserves_verifiability(monkeypatch, tmp_path: Path):
    """Persisting and reloading a bundle (common nightly_verify.py path)
    must not break signature verification."""
    _clear_signer_env(monkeypatch)
    priv, _ = Ed25519Signer.generate_keypair(tmp_path)
    monkeypatch.setenv(ENV_ED25519_KEY, str(priv))

    original = _bundle()
    d = original.to_dict()
    # Reconstruct — note ScopeLock and WitnessResult are nested dataclasses;
    # we reuse the originals here since serialization of those is out of
    # scope for this test. The key property is: signature fields survive.
    reloaded = CertBundle(
        project_id=d["project_id"],
        scope_lock=original.scope_lock,
        witness_results=original.witness_results,
        verdict=d["verdict"],
        arbitration_reason=d["arbitration_reason"],
        timestamp=d["timestamp"],
        bundle_hash=d["bundle_hash"],
        bundle_signature=d["bundle_signature"],
        signature_method=d["signature_method"],
        signature_public_key=d["signature_public_key"],
    )
    assert reloaded.verify_signature() is True
    assert reloaded.bundle_signature == original.bundle_signature
    assert reloaded.signature_method == original.signature_method
