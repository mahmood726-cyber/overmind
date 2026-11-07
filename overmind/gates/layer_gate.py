"""Gate 2 — the three-layer coverage gate. F1's fix (the one I got wrong x3).

F1: I reported a single SOURCE'S ceiling as the METHOD'S limit three times —
"14% recall" (registry only; abstracts gave 91%), "17% cell-exact" (counted
trials whose data we never had), "94% non-adjudicable" (asked only the registry;
the abstract had the counts).

The fix: any coverage/accuracy/recall/adjudicability claim must DECLARE the
evidence layers it queried, and this gate REFUSES the claim if an applicable
layer was not queried. It is impossible to say "17% cell-exact" without the
tool asking: did you try the abstract? the OA table?

This is ranked high because it is the difference, for a Makerere researcher,
between "the method can only reach 14%" (false, discouraging) and "the registry
reaches 14% but the abstract reaches 91%" (true, actionable).
"""
from __future__ import annotations

import re

from .contract import Claim, ClaimType, SourceTier

# A POINT claim describes one number from one place. If its TEXT uses aggregate /
# ceiling language, it is an aggregate claim mislabeled to dodge the layer gate
# (Codex 2026-07-13). Refuse and force correct typing.
_AGGREGATE_LANG = re.compile(
    r"\b(recall|coverage|cell-?exact|adjudicab|% of|percent of|proportion of|"
    r"ceiling|method limit|overall|across (all )?trials|poolab)\w*",
    re.IGNORECASE,
)

# For each aggregate claim type, the layers that MUST have been queried before
# the number is allowed to stand as a property of the METHOD (not one source).
# Registry alone can never bound recall/accuracy: the free abstract and OA full
# text routinely carry numbers the registry omits.
APPLICABLE_LAYERS: dict[ClaimType, tuple[SourceTier, ...]] = {
    ClaimType.RECALL:         (SourceTier.ABSTRACT, SourceTier.OA_FULLTEXT),
    ClaimType.ACCURACY:       (SourceTier.ABSTRACT, SourceTier.OA_FULLTEXT),
    ClaimType.COVERAGE:       (SourceTier.REGISTRY, SourceTier.ABSTRACT, SourceTier.OA_FULLTEXT),
    ClaimType.ADJUDICABILITY: (SourceTier.REGISTRY, SourceTier.ABSTRACT),
}

# Human-readable nudges so the refusal names the missing layer, not just fails.
_LAYER_QUESTION = {
    SourceTier.REGISTRY:    "did you check the registry posted result?",
    SourceTier.ABSTRACT:    "did you try the abstract? (PubMed carries ~91% of these)",
    SourceTier.OA_FULLTEXT: "did you try the OA full text / extracted table?",
}


class LayerCoverageError(RuntimeError):
    """Raised when an aggregate claim did not query an applicable evidence layer."""


def guard_layers(claim: Claim) -> Claim:
    """Fail closed unless every applicable layer for this claim type appears in
    ``claim.layers_queried``. POINT claims are pass-through (they describe one
    number from one place, not a property of the method)."""
    required = APPLICABLE_LAYERS.get(claim.claim_type)
    if not required:
        # Guard against mislabeling: a POINT/NOVELTY claim whose TEXT is
        # aggregate ("recall", "% of trials", "cell-exact", "ceiling") is an
        # aggregate claim wearing the wrong type to skip the layer requirement.
        if claim.claim_type in (ClaimType.POINT, ClaimType.NOVELTY) \
                and _AGGREGATE_LANG.search(claim.text or ""):
            raise LayerCoverageError(
                f"BLOCKED: claim {claim.text!r} is typed {claim.claim_type.value} "
                f"but its text is aggregate language — retype it as "
                f"recall/coverage/accuracy/adjudicability so the layer gate "
                f"applies. Mislabeling as POINT to skip layer checks is the F1 "
                f"bypass."
            )
        return claim  # genuine POINT / NOVELTY: not an aggregate-over-sources claim
    queried = set(claim.layers_queried)
    missing = [layer for layer in required if layer not in queried]
    if missing:
        questions = "; ".join(_LAYER_QUESTION.get(m, m.value) for m in missing)
        raise LayerCoverageError(
            f"BLOCKED: {claim.claim_type.value} claim {claim.text!r} = "
            f"{claim.value!r} declared layers {sorted(l.value for l in queried) or '[]'} "
            f"but did NOT query {[m.value for m in missing]}. "
            f"This is the F1 failure: a single source's ceiling is not the "
            f"method's limit. Before this number can be reported — {questions}"
        )
    return claim
