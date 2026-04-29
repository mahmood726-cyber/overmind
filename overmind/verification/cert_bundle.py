"""Arbitrator (fail-closed verdict logic) and CertBundle (signed verification output).

Signing model (per `lessons.md#cryptography--signing-learned-2026-04-14` +
ROADMAP.md#1 landing 2026-04-18):

  - `bundle_hash` is a truncated SHA256 over the canonical payload. Integrity /
    cache key only (nightly_verify.py uses it to skip unchanged inputs). NOT
    a signature.
  - `bundle_signature` + `signature_method` (+ `signature_public_key` for
    asymmetric methods) together form the authenticity proof. A third party
    that mutates a bundle JSON on disk cannot recompute the signature without
    the appropriate key material.

Signer selection is delegated to `overmind.verification.signers.select_signer()`,
which picks among: ed25519 (preferred default, local keypair, no shared secret),
HMAC-SHA256 (legacy, TRUTHCERT_HMAC_KEY), sigstore (OIDC keyless, CI / release
only), or UnsignedSigner (dev fallback). See `signers.py` for precedence rules.

Backward compatibility:
  - Bundles on disk from pre-signers days have `bundle_signature` (HMAC hex)
    and NO `signature_method` field. `verify_signature()` treats an empty
    method with a non-empty signature as legacy HMAC.
  - The `_HMAC_ENV_VAR` constant is kept as an alias for test imports that
    predate the refactor.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from overmind.verification.scope_lock import ScopeLock, WitnessResult
from overmind.verification.signers import (
    ENV_HMAC_KEY as _HMAC_ENV_VAR,
    SignResult,
    UnsignedSigner,
    select_signer,
    verify_result,
)


_log = logging.getLogger(__name__)
# Module-level "warned once" flag. Not thread-safe by design — nightly_verify
# and the on-demand CLI both run sequentially. If this module ever moves
# into a multi-threaded producer (e.g. parallel portfolio verification),
# replace with `threading.Lock` + `bool` or an `atomic_flag`. Review P2-6.
_warned_missing_signer = False


def _warn_once_unsigned() -> None:
    global _warned_missing_signer
    if not _warned_missing_signer:
        _log.warning(
            "No signer configured (OVERMIND_ED25519_KEY / TRUTHCERT_HMAC_KEY / "
            "SIGSTORE_ID_TOKEN); cert bundles will be unsigned. Set one before "
            "any release-grade verification."
        )
        _warned_missing_signer = True


class Arbitrator:
    def arbitrate(self, results: list[WitnessResult]) -> tuple[str, str]:
        non_skip = [r for r in results if r.verdict != "SKIP"]
        skipped = [r for r in results if r.verdict == "SKIP"]

        if len(non_skip) == 0:
            return "SKIP", "All witnesses skipped"

        if len(non_skip) == 1:
            v = non_skip[0].verdict
            return v, f"Single witness: {non_skip[0].witness_type} {v}"

        verdicts = {r.verdict for r in non_skip}

        if verdicts == {"PASS"}:
            # Tier-3 projects (high-risk + math ≥10) get a numerical witness.
            # If the numerical witness SKIPPED because the baseline file was
            # missing, the project is NOT release-verified — downgrade to
            # UNVERIFIED (distinct from plain PASS / CERTIFIED / SKIP).
            # Per testing.md: "A numerical witness SKIP because the baseline
            # is missing is not a release pass and does not justify promoting
            # the project status."
            numerical_skipped = any(r.witness_type == "numerical" for r in skipped)
            if numerical_skipped:
                return "UNVERIFIED", (
                    f"{len(non_skip)}/{len(non_skip)} witnesses PASS but numerical "
                    f"witness SKIPPED (baseline missing) — NOT a release pass"
                )
            return "CERTIFIED", f"{len(non_skip)}/{len(non_skip)} witnesses agree PASS"

        if verdicts == {"FAIL"}:
            types = ", ".join(r.witness_type for r in non_skip)
            return "FAIL", f"All witnesses FAIL: {types}"

        pass_witnesses = [r.witness_type for r in non_skip if r.verdict == "PASS"]
        fail_witnesses = [r.witness_type for r in non_skip if r.verdict == "FAIL"]
        return "REJECT", (
            f"Witnesses disagree: {', '.join(pass_witnesses)} PASS "
            f"vs {', '.join(fail_witnesses)} FAIL"
        )


@dataclass
class CertBundle:
    project_id: str
    scope_lock: ScopeLock
    witness_results: list[WitnessResult]
    verdict: str
    arbitration_reason: str
    timestamp: str
    bundle_hash: str = ""
    bundle_signature: str = ""
    signature_method: str = ""       # "hmac" | "ed25519" | "sigstore" | "none" | ""
    signature_public_key: str = ""   # base64 for ed25519; cert PEM for sigstore; empty otherwise
    failure_class: str | None = None  # from failure_taxonomy; None when CERTIFIED/PASS

    def __post_init__(self) -> None:
        if not self.bundle_hash:
            self.bundle_hash = self._compute_hash()
        # Only sign if nothing is already set — allows deserialized bundles to
        # keep their stored signature.method.public_key triple untouched.
        if not self.bundle_signature and not self.signature_method:
            self._sign()

    def _canonical_payload(self) -> bytes:
        # Excluded fields: bundle_hash + bundle_signature + signature_method +
        # signature_public_key (chicken-and-egg on sign), and failure_class
        # (nightly may re-classify without invalidating the signature).
        payload = {
            "project_id": self.project_id,
            "scope_lock": _frozen_to_dict(self.scope_lock),
            "witness_results": [_frozen_to_dict(w) for w in self.witness_results],
            "verdict": self.verdict,
            "arbitration_reason": self.arbitration_reason,
            "timestamp": self.timestamp,
        }
        return json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")

    def _compute_hash(self) -> str:
        return hashlib.sha256(self._canonical_payload()).hexdigest()[:16]

    def _sign(self) -> None:
        """Populate bundle_signature + signature_method + signature_public_key.

        Dev-mode fallback: if no signer is configured, leave all three empty
        (matches pre-2026-04-18 dev behavior — the bundle is still usable
        for cache-skip via bundle_hash, but verify_signature() returns False).
        """
        signer = select_signer()
        if isinstance(signer, UnsignedSigner):
            _warn_once_unsigned()
            return
        result = signer.sign(self._canonical_payload())
        self.bundle_signature = result.signature
        self.signature_method = result.method
        self.signature_public_key = result.public_key

    def verify_signature(self) -> bool:
        """Constant-time signature verification against the current payload.

        Returns True iff the stored signature matches. Dispatches on
        signature_method. Legacy bundles with no method recorded are
        treated as HMAC (pre-2026-04-18 default).

        Callers that require a signed bundle MUST treat False as failure.

        IMPORTANT: signature alone is NOT sufficient to gate decisions —
        an attacker with a copy of an old PASS bundle can replay it
        unchanged (HMAC stays valid). Pair with `verify_freshness()` for
        replay protection. See lessons.md#replay-protection-2026-04-29.
        """
        if not self.bundle_signature:
            return False
        method = self.signature_method or "hmac"  # legacy default
        result = SignResult(
            method=method,
            signature=self.bundle_signature,
            public_key=self.signature_public_key,
        )
        return verify_result(self._canonical_payload(), result)

    def verify_freshness(self, max_age_seconds: int) -> bool:
        """Check that bundle timestamp is within max_age_seconds of now (UTC).

        REPLAY-PROTECTION complement to verify_signature(). HMAC/Ed25519
        prove authenticity (this bundle was minted with the legitimate
        key) but NOT recency (an attacker who acquired any old PASS
        bundle can replay it as if fresh).

        Returns True iff:
          - timestamp parses as ISO-8601, AND
          - timestamp is in the past (no future-dated bundles), AND
          - age (now - timestamp) <= max_age_seconds.

        Callers gating release/CI decisions on a bundle MUST verify
        BOTH signature AND freshness. v6 benchmark gap #1 (2026-04-29).
        """
        if not self.timestamp:
            return False
        try:
            ts_str = self.timestamp.replace("Z", "+00:00")
            ts = datetime.fromisoformat(ts_str)
        except (ValueError, AttributeError):
            return False
        if ts.tzinfo is None:
            # Naive timestamp — treat as UTC.
            ts = ts.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age_seconds = (now - ts).total_seconds()
        if age_seconds < 0:
            # Future-dated bundle — clock skew or forgery; reject.
            return False
        return age_seconds <= max_age_seconds

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "scope_lock": _frozen_to_dict(self.scope_lock),
            "witness_results": [_frozen_to_dict(w) for w in self.witness_results],
            "verdict": self.verdict,
            "arbitration_reason": self.arbitration_reason,
            "timestamp": self.timestamp,
            "bundle_hash": self.bundle_hash,
            "bundle_signature": self.bundle_signature,
            "signature_method": self.signature_method,
            "signature_public_key": self.signature_public_key,
            "failure_class": self.failure_class,
        }


def _frozen_to_dict(obj) -> dict:
    if hasattr(obj, "__dataclass_fields__"):
        result = {}
        for name in obj.__dataclass_fields__:
            val = getattr(obj, name)
            if isinstance(val, tuple):
                val = list(val)
            result[name] = val
        return result
    return dict(obj)
