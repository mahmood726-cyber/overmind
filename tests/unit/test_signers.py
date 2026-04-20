"""Tests for pluggable CertBundle signers.

Covers HMAC (backward compat), Ed25519 (new default), sigstore
(mocked — real sign requires OIDC), and UnsignedSigner. Plus the
select_signer() factory precedence.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from overmind.verification.signers import (
    ENV_ED25519_KEY,
    ENV_HMAC_KEY,
    ENV_METHOD,
    ENV_SIGSTORE_TOKEN,
    Ed25519Signer,
    HmacSigner,
    SignResult,
    UnsignedSigner,
    select_signer,
)


PAYLOAD = b'{"project_id":"demo","verdict":"CERTIFIED"}'


# --- HMAC (legacy) --------------------------------------------------

def test_hmac_sign_verify_roundtrip():
    s = HmacSigner(b"super-secret-key")
    result = s.sign(PAYLOAD)
    assert result.method == "hmac"
    assert len(result.signature) == 64  # sha256 hex
    assert s.verify(PAYLOAD, result) is True


def test_hmac_verify_rejects_tampered_payload():
    s = HmacSigner(b"key")
    result = s.sign(PAYLOAD)
    assert s.verify(PAYLOAD + b"tampered", result) is False


def test_hmac_verify_rejects_wrong_key():
    s1 = HmacSigner(b"key-a")
    s2 = HmacSigner(b"key-b")
    result = s1.sign(PAYLOAD)
    assert s2.verify(PAYLOAD, result) is False


def test_hmac_verify_rejects_non_hmac_result():
    s = HmacSigner(b"key")
    fake = SignResult(method="ed25519", signature="x", public_key="y")
    assert s.verify(PAYLOAD, fake) is False


# --- Ed25519 --------------------------------------------------------

def test_ed25519_sign_verify_roundtrip(tmp_path: Path):
    priv, pub = Ed25519Signer.generate_keypair(tmp_path)
    s = Ed25519Signer.from_key_path(priv)
    result = s.sign(PAYLOAD)
    assert result.method == "ed25519"
    assert result.public_key != ""
    assert s.verify(PAYLOAD, result) is True


def test_ed25519_verify_rejects_tampered_payload(tmp_path: Path):
    priv, _ = Ed25519Signer.generate_keypair(tmp_path)
    s = Ed25519Signer.from_key_path(priv)
    result = s.sign(PAYLOAD)
    assert s.verify(PAYLOAD + b"tampered", result) is False


def test_ed25519_verify_rejects_other_signer_output(tmp_path: Path):
    """Key from one signer can't verify output from another."""
    priv1, _ = Ed25519Signer.generate_keypair(tmp_path / "a")
    priv2, _ = Ed25519Signer.generate_keypair(tmp_path / "b")
    s1 = Ed25519Signer.from_key_path(priv1)
    s2 = Ed25519Signer.from_key_path(priv2)
    # Sign with s1. s2 has a DIFFERENT private key; but each SignResult
    # includes its own public_key — so s2.verify(result_from_s1) actually
    # uses s1's public key and should VERIFY (public key travels with
    # signature, this is working as intended).
    r = s1.sign(PAYLOAD)
    assert s2.verify(PAYLOAD, r) is True
    # But forging: substitute s2's pubkey into s1's signature result
    # and re-verify — signature won't match under a different pubkey.
    r2 = s2.sign(PAYLOAD)
    forged = SignResult(
        method="ed25519",
        signature=r.signature,      # s1's sig
        public_key=r2.public_key,   # but s2's pubkey
    )
    assert s2.verify(PAYLOAD, forged) is False


def test_ed25519_generated_keypair_files_exist(tmp_path: Path):
    priv, pub = Ed25519Signer.generate_keypair(tmp_path)
    assert priv.is_file()
    assert pub.is_file()
    assert len(priv.read_bytes()) == 32  # Raw 32-byte Ed25519 private key
    assert len(pub.read_bytes()) == 32   # Raw 32-byte Ed25519 public key


def test_ed25519_from_key_path_missing_raises(tmp_path: Path):
    with pytest.raises((FileNotFoundError, OSError)):
        Ed25519Signer.from_key_path(tmp_path / "nope")


# --- Unsigned -------------------------------------------------------

def test_unsigned_signer_always_unverified():
    s = UnsignedSigner()
    result = s.sign(PAYLOAD)
    assert result.method == "none"
    assert result.signature == ""
    # Unsigned bundles never verify — by design. Callers must treat
    # this as "unsafe to trust".
    assert s.verify(PAYLOAD, result) is False


# --- Factory precedence --------------------------------------------

def test_select_signer_prefers_explicit_method_none(monkeypatch):
    monkeypatch.setenv(ENV_METHOD, "none")
    monkeypatch.delenv(ENV_HMAC_KEY, raising=False)
    monkeypatch.delenv(ENV_ED25519_KEY, raising=False)
    s = select_signer()
    assert s.method_name == "none"


def test_select_signer_auto_prefers_ed25519_over_hmac(monkeypatch, tmp_path: Path):
    priv, _ = Ed25519Signer.generate_keypair(tmp_path)
    monkeypatch.delenv(ENV_METHOD, raising=False)
    monkeypatch.setenv(ENV_ED25519_KEY, str(priv))
    monkeypatch.setenv(ENV_HMAC_KEY, "key")
    s = select_signer()
    assert s.method_name == "ed25519"


def test_select_signer_auto_falls_back_to_hmac(monkeypatch):
    monkeypatch.delenv(ENV_METHOD, raising=False)
    monkeypatch.delenv(ENV_ED25519_KEY, raising=False)
    monkeypatch.setenv(ENV_HMAC_KEY, "key")
    monkeypatch.delenv(ENV_SIGSTORE_TOKEN, raising=False)
    s = select_signer()
    assert s.method_name == "hmac"


def test_select_signer_auto_unsigned_when_no_config(monkeypatch):
    monkeypatch.delenv(ENV_METHOD, raising=False)
    monkeypatch.delenv(ENV_ED25519_KEY, raising=False)
    monkeypatch.delenv(ENV_HMAC_KEY, raising=False)
    monkeypatch.delenv(ENV_SIGSTORE_TOKEN, raising=False)
    s = select_signer()
    assert s.method_name == "none"


def test_select_signer_explicit_hmac_missing_key_raises(monkeypatch):
    monkeypatch.setenv(ENV_METHOD, "hmac")
    monkeypatch.delenv(ENV_HMAC_KEY, raising=False)
    with pytest.raises(RuntimeError, match=ENV_HMAC_KEY):
        select_signer()


def test_select_signer_explicit_sigstore_missing_token_raises(monkeypatch):
    monkeypatch.setenv(ENV_METHOD, "sigstore")
    monkeypatch.delenv(ENV_SIGSTORE_TOKEN, raising=False)
    with pytest.raises(RuntimeError, match=ENV_SIGSTORE_TOKEN):
        select_signer()


def test_select_signer_auto_ed25519_broken_path_fails_closed(monkeypatch, tmp_path: Path):
    """Review P1-1: a set-but-broken OVERMIND_ED25519_KEY must FAIL CLOSED
    with FileNotFoundError, NOT silently fall back to HMAC. Rationale:
    silent downgrade-from-Ed25519-to-HMAC is the exact 'policy says signed,
    reality ships X' failure mode the 2026-04-19 security review flagged.
    A broken primary-method config is an operator bug that must surface,
    not be masked by a weaker backup."""
    monkeypatch.delenv(ENV_METHOD, raising=False)
    monkeypatch.setenv(ENV_ED25519_KEY, str(tmp_path / "nonexistent_key"))
    monkeypatch.setenv(ENV_HMAC_KEY, "would-be-fallback")
    with pytest.raises((FileNotFoundError, OSError)):
        select_signer()


def test_select_signer_auto_ed25519_malformed_file_fails_closed(monkeypatch, tmp_path: Path):
    """Review P2-R2: sibling to the broken-path test. If the key file EXISTS
    but contains junk (wrong length, not PEM), Ed25519PrivateKey raises
    ValueError — also not RuntimeError, so also propagates. Must NOT silently
    downgrade to HMAC. Covers the 'file exists but is garbage' config bug
    separately from 'file doesn't exist'."""
    bogus = tmp_path / "bogus_key"
    bogus.write_bytes(b"\x00" * 100)  # 100 bytes — not 32, not a PEM envelope
    monkeypatch.delenv(ENV_METHOD, raising=False)
    monkeypatch.setenv(ENV_ED25519_KEY, str(bogus))
    monkeypatch.setenv(ENV_HMAC_KEY, "would-be-fallback")
    with pytest.raises(ValueError):
        select_signer()
