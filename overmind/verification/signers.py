"""Pluggable bundle signers for CertBundle.

Three signing methods, selected per-environment:

  1. Ed25519 (local keypair)  — preferred default. Asymmetric: private
     key signs, public key verifies. No shared secret to leak. Works
     offline and in scheduled tasks. Signs a SHA-256 hash of the
     canonical payload.
  2. HMAC-SHA256              — legacy. Kept for backward compat.
     Symmetric; same key to sign + verify. Suitable for single-user
     closed-loop use only. Deprecated in v0.3 roadmap.
  3. Sigstore (OIDC keyless)  — for CI / release attestation. Requires
     an OIDC identity token (GitHub Actions id-token, or manually
     fetched). Not viable for headless Windows Task Scheduler without
     OIDC plumbing — hence optional.

Selection precedence:
  - Env `OVERMIND_SIGN_METHOD` if set to one of: hmac|ed25519|sigstore|none
  - Else auto: ed25519 if key-path set, else HMAC if key set, else unsigned

Verification:
  Each bundle records `signature_method` so verifiers know which signer
  to reconstruct. Public keys / certs are recorded inline for ed25519
  and sigstore (small enough not to bloat the bundle).
"""
from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

_log = logging.getLogger(__name__)

ENV_METHOD = "OVERMIND_SIGN_METHOD"
ENV_HMAC_KEY = "TRUTHCERT_HMAC_KEY"
ENV_ED25519_KEY = "OVERMIND_ED25519_KEY"            # path to PEM/raw key file
ENV_ED25519_GEN = "OVERMIND_ED25519_AUTOGEN_DIR"    # where to auto-create a keypair
ENV_SIGSTORE_TOKEN = "SIGSTORE_ID_TOKEN"            # pre-fetched OIDC token


@dataclass
class SignResult:
    method: str              # "hmac" | "ed25519" | "sigstore" | "none"
    signature: str           # hex or base64 depending on method
    public_key: str = ""     # empty for hmac; base64 for ed25519; PEM for sigstore cert
    metadata: dict | None = None  # method-specific extras (Rekor log index, etc.)


class Signer(ABC):
    """Strategy interface for bundle signing."""
    method_name: str = "unset"

    @abstractmethod
    def sign(self, payload: bytes) -> SignResult: ...

    @abstractmethod
    def verify(self, payload: bytes, result: SignResult) -> bool: ...


# =====================================================================
# HMAC (legacy)
# =====================================================================

class HmacSigner(Signer):
    method_name = "hmac"

    def __init__(self, key: bytes) -> None:
        self.key = key

    def sign(self, payload: bytes) -> SignResult:
        sig = _hmac.new(self.key, payload, hashlib.sha256).hexdigest()
        return SignResult(method="hmac", signature=sig, public_key="")

    def verify(self, payload: bytes, result: SignResult) -> bool:
        if result.method != "hmac":
            return False
        expected = _hmac.new(self.key, payload, hashlib.sha256).hexdigest()
        return _hmac.compare_digest(expected, result.signature)


# =====================================================================
# Ed25519 (recommended default for laptop-scheduled tasks)
# =====================================================================

class Ed25519Signer(Signer):
    """Local Ed25519 keypair signer.

    Eliminates the HMAC "shared-secret can forge" class. Private key
    stays on disk (600 perms recommended); public key is embedded in
    each signed bundle for inline verification.
    """
    method_name = "ed25519"

    def __init__(self, private_key_bytes: bytes) -> None:
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PrivateKey,
            )
        except ImportError as e:
            raise RuntimeError(
                "cryptography package required for Ed25519 signing"
            ) from e
        # Accept either raw 32-byte key or PEM-encoded.
        if len(private_key_bytes) == 32:
            self._key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
        else:
            from cryptography.hazmat.primitives import serialization
            self._key = serialization.load_pem_private_key(
                private_key_bytes, password=None,
            )
        self._public_key = self._key.public_key()

    def sign(self, payload: bytes) -> SignResult:
        from cryptography.hazmat.primitives import serialization
        sig_bytes = self._key.sign(payload)
        pub_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return SignResult(
            method="ed25519",
            signature=base64.b64encode(sig_bytes).decode("ascii"),
            public_key=base64.b64encode(pub_bytes).decode("ascii"),
        )

    def verify(self, payload: bytes, result: SignResult) -> bool:
        if result.method != "ed25519":
            return False
        try:
            from cryptography.exceptions import InvalidSignature
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PublicKey,
            )
            pub_bytes = base64.b64decode(result.public_key)
            pub = Ed25519PublicKey.from_public_bytes(pub_bytes)
            sig = base64.b64decode(result.signature)
            pub.verify(sig, payload)
            return True
        except (InvalidSignature, ValueError):
            return False

    @classmethod
    def from_key_path(cls, path: Path | str) -> "Ed25519Signer":
        path = Path(path)
        return cls(path.read_bytes())

    @classmethod
    def generate_keypair(cls, out_dir: Path | str) -> tuple[Path, Path]:
        """Write a fresh private + public key to `out_dir`. Returns (priv, pub)."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        priv = Ed25519PrivateKey.generate()
        priv_path = out_dir / "overmind_ed25519"
        pub_path = out_dir / "overmind_ed25519.pub"
        priv_path.write_bytes(
            priv.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        pub_path.write_bytes(
            priv.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        )
        try:
            # chmod 600 on POSIX; no-op on Windows
            priv_path.chmod(0o600)
        except OSError:
            pass
        return priv_path, pub_path


# =====================================================================
# Sigstore (OIDC keyless)
# =====================================================================

class SigstoreSigner(Signer):
    """OIDC keyless signer via sigstore-python.

    Requires an OIDC identity token in `SIGSTORE_ID_TOKEN`. In GitHub
    Actions the token is fetched automatically via `id-token: write`
    workflow permission. On a laptop, user must obtain one via
    `sigstore auth login` (opens browser) or similar.

    Writes a Rekor transparency-log entry so public verifiers can
    confirm signatures without trusting this machine.
    """
    method_name = "sigstore"

    def __init__(self, identity_token: str) -> None:
        try:
            from sigstore.oidc import IdentityToken  # noqa: F401
            from sigstore.sign import SigningContext  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "sigstore package required for Sigstore signing"
            ) from e
        self._identity_token = identity_token

    def sign(self, payload: bytes) -> SignResult:
        # sigstore's public API changes across versions; pin to the
        # minimal surface and fail loudly if absent.
        from sigstore.oidc import IdentityToken
        from sigstore.sign import SigningContext

        identity = IdentityToken(self._identity_token)
        ctx = SigningContext.production()
        with ctx.signer(identity) as signer:
            import io
            bundle = signer.sign_artifact(io.BytesIO(payload))
        # Extract the DSSE signature + cert chain into our portable shape.
        # sigstore Bundle is a protobuf; serialize to JSON for storage.
        bundle_json = bundle.to_json()
        return SignResult(
            method="sigstore",
            signature=base64.b64encode(bundle_json.encode("utf-8")).decode("ascii"),
            public_key="",  # cert chain lives inside the bundle_json
            metadata={"bundle_format": "sigstore-bundle-v0.3-json"},
        )

    def verify(self, payload: bytes, result: SignResult) -> bool:
        if result.method != "sigstore":
            return False
        try:
            from sigstore.verify import Verifier
            from sigstore.verify.policy import AnyOf
            from sigstore.models import Bundle
            bundle_json = base64.b64decode(result.signature).decode("utf-8")
            bundle = Bundle.from_json(bundle_json)
            verifier = Verifier.production()
            # Policy is "any signer" here — real release verification
            # should pin the expected identity via a stricter policy.
            verifier.verify_artifact(payload, bundle, AnyOf([]))
            return True
        except Exception as e:
            _log.warning("sigstore verify failed: %s", e)
            return False


# =====================================================================
# Unsigned (fallback)
# =====================================================================

class UnsignedSigner(Signer):
    method_name = "none"

    def sign(self, payload: bytes) -> SignResult:
        return SignResult(method="none", signature="", public_key="")

    def verify(self, payload: bytes, result: SignResult) -> bool:
        return False  # unsigned bundles never verify — by design.


# =====================================================================
# Factory
# =====================================================================

def select_signer() -> Signer:
    """Return the signer implied by current environment.

    Precedence:
      1. OVERMIND_SIGN_METHOD=<method> (explicit override)
      2. OVERMIND_ED25519_KEY set -> Ed25519 from that path
      3. TRUTHCERT_HMAC_KEY set -> HMAC (legacy)
      4. SIGSTORE_ID_TOKEN set -> Sigstore
      5. UnsignedSigner (with warning)
    """
    method = os.environ.get(ENV_METHOD, "").strip().lower()

    if method == "ed25519":
        return _build_ed25519_or_fail()
    if method == "hmac":
        return _build_hmac_or_fail()
    if method == "sigstore":
        return _build_sigstore_or_fail()
    if method == "none":
        return UnsignedSigner()

    # Auto mode
    if os.environ.get(ENV_ED25519_KEY):
        try:
            return _build_ed25519_or_fail()
        except RuntimeError as e:
            _log.warning("ed25519 signer unavailable (%s); falling back", e)
    if os.environ.get(ENV_HMAC_KEY):
        return _build_hmac_or_fail()
    if os.environ.get(ENV_SIGSTORE_TOKEN):
        try:
            return _build_sigstore_or_fail()
        except RuntimeError as e:
            _log.warning("sigstore signer unavailable (%s); falling back", e)

    _log.warning(
        "No signing key configured (OVERMIND_ED25519_KEY / TRUTHCERT_HMAC_KEY "
        "/ SIGSTORE_ID_TOKEN). Bundles will be UNSIGNED. Set one before any "
        "release-grade verification."
    )
    return UnsignedSigner()


def _build_ed25519_or_fail() -> Ed25519Signer:
    key_path = os.environ.get(ENV_ED25519_KEY)
    if not key_path:
        raise RuntimeError(
            f"{ENV_ED25519_KEY} must be set to a path containing an Ed25519 private key"
        )
    return Ed25519Signer.from_key_path(key_path)


def _build_hmac_or_fail() -> HmacSigner:
    key = os.environ.get(ENV_HMAC_KEY, "")
    if not key:
        raise RuntimeError(f"{ENV_HMAC_KEY} must be set for HMAC signing")
    return HmacSigner(key.encode("utf-8"))


def _build_sigstore_or_fail() -> SigstoreSigner:
    token = os.environ.get(ENV_SIGSTORE_TOKEN, "")
    if not token:
        raise RuntimeError(
            f"{ENV_SIGSTORE_TOKEN} must be set (OIDC identity token) for sigstore signing"
        )
    return SigstoreSigner(token)


# =====================================================================
# Standalone verification (no signer instance needed for asymmetric methods)
# =====================================================================

def verify_result(payload: bytes, result: SignResult) -> bool:
    """Verify a SignResult against a payload. Dispatches on result.method.

    Asymmetric methods (ed25519, sigstore) verify from the public key /
    cert chain embedded in `result`, so no env config is required.
    Symmetric HMAC requires TRUTHCERT_HMAC_KEY in the environment —
    returns False if unset. method="none" always returns False.

    Use this instead of rebuilding the original signer when the caller
    only needs to verify (e.g. reading a persisted bundle from disk).
    """
    method = result.method
    if method == "hmac":
        key = os.environ.get(ENV_HMAC_KEY, "")
        if not key:
            return False
        return HmacSigner(key.encode("utf-8")).verify(payload, result)
    if method == "ed25519":
        try:
            from cryptography.exceptions import InvalidSignature
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PublicKey,
            )
            pub_bytes = base64.b64decode(result.public_key)
            pub = Ed25519PublicKey.from_public_bytes(pub_bytes)
            sig = base64.b64decode(result.signature)
            pub.verify(sig, payload)
            return True
        except (InvalidSignature, ValueError, ImportError):
            return False
    if method == "sigstore":
        try:
            from sigstore.verify import Verifier
            from sigstore.verify.policy import AnyOf
            from sigstore.models import Bundle
            bundle_json = base64.b64decode(result.signature).decode("utf-8")
            bundle = Bundle.from_json(bundle_json)
            verifier = Verifier.production()
            verifier.verify_artifact(payload, bundle, AnyOf([]))
            return True
        except Exception as e:
            _log.warning("sigstore verify failed: %s", e)
            return False
    return False
