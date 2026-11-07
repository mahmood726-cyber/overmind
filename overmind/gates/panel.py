"""Gate 4 — the cross-family panel, mandatory and fail-closed. F4 / F6 / F7.

This protects the one component measured to be load-bearing: cross-FAMILY review
caught five errors in a single day that a second copy of the same model would
have waved through. The external reviewers warned it is an alarm, not a
foundation — so here it is made rigorous, not trusted blindly:

  - ABSTENTION IS NEVER A VOTE (F6). A dead vendor that returns empty and exits 0
    contributes nothing; its silence cannot become a consensus vote.
  - >=2 DISTINCT FAMILIES are required on any claim that flatters the user or
    confirms our own hypothesis (F4). A second same-family voice does not count.
  - NO NOVELTY CLAIM SHIPS without an adversarial prior-art pass by a DIFFERENT
    family (F7). Same-family "looks novel to me" is worthless.

Family is the unit of decorrelation: anthropic, openai, google are three
independent families; two anthropic votes are ONE family.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .contract import Claim, ClaimType


class Verdict(str, Enum):
    CONFIRM = "confirm"
    REFUTE = "refute"
    ABSTAIN = "abstain"   # explicit "I don't know" — still not a vote either way


@dataclass(frozen=True, slots=True)
class Vote:
    family: str                 # "anthropic" | "openai" | "google" | ...
    verdict: Verdict
    detail: str = ""
    empty: bool = False         # vendor returned empty output (dead/timeout)

    @property
    def counts(self) -> bool:
        """A vote counts only if the vendor actually answered confirm/refute."""
        return (not self.empty) and self.verdict in (Verdict.CONFIRM, Verdict.REFUTE)


class PanelError(RuntimeError):
    """Base for panel refusals — always fail closed."""


class AbstentionError(PanelError):
    """Raised if the panel would have to rely on an abstaining/empty vote."""


def _real_votes(votes) -> list[Vote]:
    return [v for v in votes if v.counts]


def _families(votes) -> set[str]:
    return {v.family for v in votes}


def adjudicate(claim: Claim, votes, *, claimant_family: str = "anthropic") -> dict:
    """Fail closed unless the claim clears the family requirements for its risk.

    Returns a summary dict on success; raises PanelError otherwise. `votes` may
    include abstentions and empty (dead-vendor) votes — they are dropped before
    any counting, so silence can never approve a claim.
    """
    real = _real_votes(votes)
    dropped = [v for v in votes if not v.counts]

    # F6: a claim with no real votes at all cannot pass on abstentions.
    needs_panel = (claim.flatters_user or claim.confirms_hypothesis
                   or claim.claim_type is ClaimType.NOVELTY)
    if needs_panel and not real:
        raise AbstentionError(
            f"BLOCKED: {claim.text!r} needs cross-family review but every vote "
            f"was empty/abstain ({[v.family for v in dropped]}). Abstention is "
            f"not a vote — a dead vendor's silence cannot approve this."
        )

    # F4: flattering / self-confirming claims need >=2 DISTINCT families.
    if claim.flatters_user or claim.confirms_hypothesis:
        fams = _families(real)
        if len(fams) < 2:
            raise PanelError(
                f"BLOCKED: {claim.text!r} flatters the user/us and has real "
                f"votes from only {sorted(fams) or '[]'} — >=2 distinct families "
                f"required (a second same-family voice is not decorrelation). "
                f"This is the F4 anti-sycophancy rule."
            )
        # FAIL CLOSED ON DISSENT (Codex 2026-07-13 found this hole): a single
        # CONFIRM must NOT win over another family's REFUTE. ANY counted refute
        # blocks a flattering claim — dissent is exactly the signal we cannot
        # afford to average away when the pull is to please.
        refuters = [v for v in real if v.verdict is Verdict.REFUTE]
        if refuters:
            raise PanelError(
                f"BLOCKED: {claim.text!r} flatters the user/us and was REFUTED "
                f"by {sorted({v.family for v in refuters})}. A confirm from "
                f"another family does not override cross-family dissent on a "
                f"claim we want to be true (F4)."
            )
        if not any(v.verdict is Verdict.CONFIRM for v in real):
            raise PanelError(
                f"BLOCKED: {claim.text!r} was not confirmed by the cross-family "
                f"panel ({[(v.family, v.verdict.value) for v in real]})."
            )

    # F7: novelty needs a prior-art pass from a DIFFERENT family than the claimant.
    if claim.claim_type is ClaimType.NOVELTY:
        # Any different-family REFUTE (= found prior art) is fail-closed: it only
        # takes one external family to find the Dawid-Skene reference.
        prior_art_found = [
            v for v in real
            if v.family != claimant_family and v.verdict is Verdict.REFUTE
        ]
        if prior_art_found:
            raise PanelError(
                f"BLOCKED: novelty claim {claim.text!r} — prior art found by "
                f"{sorted({v.family for v in prior_art_found})}. Not novel (F7)."
            )
        other_family_confirms = [
            v for v in real
            if v.family != claimant_family and v.verdict is Verdict.CONFIRM
        ]
        if not other_family_confirms:
            raise PanelError(
                f"BLOCKED: novelty claim {claim.text!r} has no adversarial "
                f"prior-art pass from a family other than {claimant_family!r}. "
                f"Every past novelty claim (Trialstreamer, EligMeta, "
                f"Dawid-Skene 1979) was refuted by an external family — F7."
            )

    return {
        "claim": claim.text,
        "counted_families": sorted(_families(real)),
        "dropped": [(v.family, "empty" if v.empty else v.verdict.value) for v in dropped],
        "passed": True,
    }
