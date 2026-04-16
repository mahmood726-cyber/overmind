"""Arbitrator (fail-closed verdict logic) and CertBundle (output with hash + HMAC signature).

Signing model (per `lessons.md#cryptography--signing-learned-2026-04-14`):
  - `bundle_hash` is a truncated SHA256 over the canonical payload. It is an
    integrity / cache key (used by nightly_verify.py to detect unchanged
    inputs and skip re-verification). NOT a signature.
  - `bundle_signature` is HMAC-SHA256 over the same canonical payload, keyed
    from the `TRUTHCERT_HMAC_KEY` env variable. Verifies authenticity:
    a third party that mutates a bundle JSON on disk cannot recompute the
    signature without the key.

Key sourcing rules (failure modes encoded in lessons.md):
  - Key MUST come from env or a gitignored file, NEVER from the bundle itself.
  - If env var is not set: signature is left empty and a warning is logged.
    The bundle is still usable (caches still work via bundle_hash) but is
    NOT release-grade. Production callers should set the env var.
  - Verification uses `hmac.compare_digest` (constant-time).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass

from overmind.verification.scope_lock import ScopeLock, WitnessResult


_log = logging.getLogger(__name__)
_HMAC_ENV_VAR = "TRUTHCERT_HMAC_KEY"
_warned_missing_key = False  # only warn once per process


def _get_hmac_key() -> bytes | None:
    """Return key bytes from env var, or None if unset."""
    val = os.environ.get(_HMAC_ENV_VAR, "")
    if not val:
        return None
    return val.encode("utf-8")


def _warn_once_missing_key() -> None:
    global _warned_missing_key
    if not _warned_missing_key:
        _log.warning(
            "%s not set; cert bundles will be unsigned. Set this env var "
            "before any release-grade verification.",
            _HMAC_ENV_VAR,
        )
        _warned_missing_key = True


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
    bundle_signature: str = ""  # HMAC-SHA256, empty if TRUTHCERT_HMAC_KEY unset
    failure_class: str | None = None  # from failure_taxonomy; None when CERTIFIED/PASS

    def __post_init__(self) -> None:
        if not self.bundle_hash:
            self.bundle_hash = self._compute_hash()
        if not self.bundle_signature:
            self.bundle_signature = self._compute_signature()

    def _canonical_payload(self) -> bytes:
        # failure_class is excluded so a nightly re-classifying an existing
        # bundle's failure category doesn't invalidate prior hashes/signatures.
        # bundle_signature is also excluded (chicken-and-egg).
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

    def _compute_signature(self) -> str:
        """Return HMAC-SHA256 hex over the canonical payload, or '' if no key.

        Empty signature is non-fatal (dev mode); production callers must set
        TRUTHCERT_HMAC_KEY and verify_signature() before trusting a bundle.
        """
        key = _get_hmac_key()
        if key is None:
            _warn_once_missing_key()
            return ""
        return hmac.new(key, self._canonical_payload(), hashlib.sha256).hexdigest()

    def verify_signature(self) -> bool:
        """Constant-time HMAC verification.

        Returns True iff the bundle's stored signature matches a freshly
        computed HMAC over its current payload. Returns False if the key
        is missing OR if the signature is empty OR if it doesn't match.
        Callers that require a signed bundle MUST treat False as failure.
        """
        key = _get_hmac_key()
        if key is None or not self.bundle_signature:
            return False
        expected = hmac.new(key, self._canonical_payload(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, self.bundle_signature)

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
