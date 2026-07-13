"""Mahmood's stated hypotheses, registered ONCE with pre-registered refutations.

This is the honest core of the anti-sycophancy fix: the refutation criterion for
each claim is written down HERE, before any headline is emitted, by Mahmood — not
by the lane that later happens to confirm it. Any fact whose key matches a
hypothesis's patterns (and satisfies its direction) is auto-classified as
confirming and inherits that refutation, so the cross-family verify gate fires
whether or not the emitting lane remembered to declare it.

Each entry's `direction` makes the match value-sensitive: a REFUTING result (below
the coverage threshold, an effect that crossed the null the wrong way) is NOT
mislabeled as confirming — only a genuinely confirming value trips the gate, which
is exactly when the pull to soften toward Mahmood is strongest.
"""
from __future__ import annotations

from overmind.factstore.store import FactStore

# slug -> (statement, key_patterns, refutation_criterion, direction)
HYPOTHESES = [
    dict(
        slug="abstract-first-coverage",
        statement=("Abstract-first (PubMed abstract as the dominant free layer) reaches "
                   "~80% of gold trials with usable numbers without the paywall."),
        key_patterns=["coverage.union*", "coverage.abstract_usable*", "coverage.*findability*"],
        refutation_criterion=("Union coverage (abstract ∪ OA ∪ registry) on the Cochrane "
                              "gold set falls below 0.70, OR abstract-usable < 0.60."),
        direction={"op": ">=", "threshold": 0.70},
    ),
    dict(
        slug="registry-beats-funnel-small-k",
        statement=("Registry/abstract framing recovers a real pooled effect where funnel-"
                   "based small-study correction manufactures a phantom one at small k."),
        key_patterns=["*.pooled.*", "*.rr.headline*", "*.effect.headline*"],
        refutation_criterion=("On the shared corpus, registry-frame and funnel-correction "
                              "agree within tolerance at k<10 (no phantom), OR registry-frame "
                              "sign-error rate is not lower than funnel's."),
        direction=None,  # any headline pooled effect is a confirming candidate; panel decides
    ),
    dict(
        slug="harms-completeness",
        statement=("Per-arm registry integers recover serious-harm signal that reviews lump "
                   "into a single pooled AE outcome and lose."),
        key_patterns=["harms.completeness*", "harms.asymmetry.headline*"],
        refutation_criterion=("Per-arm registry harm granularity does not exceed the review's "
                              "reported harm-term count on the matched trials."),
        direction=None,
    ),
]


def register_all(fs: FactStore) -> list[str]:
    """Register every hypothesis on the store. Idempotent (INSERT OR REPLACE).
    Returns the slugs registered."""
    for h in HYPOTHESES:
        fs.register_hypothesis(
            h["slug"], statement=h["statement"], key_patterns=h["key_patterns"],
            refutation_criterion=h["refutation_criterion"], direction=h["direction"])
    return [h["slug"] for h in HYPOTHESES]
