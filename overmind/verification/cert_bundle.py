"""Arbitrator (fail-closed verdict logic) and CertBundle (output with hash)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from overmind.verification.scope_lock import ScopeLock, WitnessResult


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
    failure_class: str | None = None  # from failure_taxonomy; None when CERTIFIED/PASS

    def __post_init__(self) -> None:
        if not self.bundle_hash:
            self.bundle_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        # failure_class is excluded from hash so a nightly re-classifying an
        # existing bundle's failure category doesn't invalidate prior hashes.
        payload = {
            "project_id": self.project_id,
            "scope_lock": _frozen_to_dict(self.scope_lock),
            "witness_results": [_frozen_to_dict(w) for w in self.witness_results],
            "verdict": self.verdict,
            "arbitration_reason": self.arbitration_reason,
            "timestamp": self.timestamp,
        }
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(encoded.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "scope_lock": _frozen_to_dict(self.scope_lock),
            "witness_results": [_frozen_to_dict(w) for w in self.witness_results],
            "verdict": self.verdict,
            "arbitration_reason": self.arbitration_reason,
            "timestamp": self.timestamp,
            "bundle_hash": self.bundle_hash,
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
