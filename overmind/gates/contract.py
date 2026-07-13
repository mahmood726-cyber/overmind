"""The typed Claim / Evidence contract.

Both external families (Codex/GPT-5, agy/Gemini), reviewing this harness blind,
independently ranked THIS as the #1 fix: a claim must not be allowed to exist
and travel before it carries typed provenance. A bare float passed between lanes
is exactly how the fake DTA70 figure and the three single-source ceilings
(F1, F2) moved undetected.

A Claim is the only thing the gates in this package accept. If you have a raw
number you want to put in front of the user, you must first wrap it here, which
forces you to answer: what is this a number OF, where did it come from, and
which evidence layers did you actually look at.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SourceTier(str, Enum):
    """Ordered by directness for open-access reconstruction (the Kampala path).

    A Makerere researcher cannot read paywalled full text; the tiers we can
    actually reach are the registry, the abstract, and OA full text. DERIVED is
    computed from other claims. SYNTHETIC is fabricated/demo data and is NEVER
    exportable — it exists only so the store can prove the taint machinery works.
    """
    REGISTRY = "registry"          # ClinicalTrials.gov / ICTRP posted result
    ABSTRACT = "abstract"          # PubMed abstract (the coverage layer)
    OA_FULLTEXT = "oa_fulltext"    # open-access full text / extracted tables
    DERIVED = "derived"            # computed from >=1 parent Claim
    SYNTHETIC = "synthetic"        # fabricated / demo — cannot cross the boundary


class ClaimType(str, Enum):
    POINT = "point"                # a single reported quantity
    RECALL = "recall"              # "we recovered X% of ..."
    COVERAGE = "coverage"          # "X% of trials are ..."
    ACCURACY = "accuracy"          # "X% cell-exact / correct"
    ADJUDICABILITY = "adjudicability"  # "X% can(not) be adjudicated"
    NOVELTY = "novelty"            # "this method is new / first / unprecedented"


@dataclass(slots=True)
class Claim:
    """A number the harness intends to put in front of the user.

    Required to be exportable: a real (non-synthetic) source tier and a
    non-empty locator. Coverage/accuracy/recall/adjudicability claims must also
    declare ``layers_queried`` (enforced by layer_gate). Anything that flatters
    the user or confirms our own hypothesis must clear the cross-family panel.
    """
    text: str                                   # what the number is OF, in words
    value: Any                                  # the number itself
    source_tier: SourceTier
    locator: str                                # e.g. "NCT01439880#om[2]" / "PMID:12#tbl2"
    claim_type: ClaimType = ClaimType.POINT
    layers_queried: tuple[SourceTier, ...] = ()
    synthetic: bool = False                     # explicit fabricated flag
    derived_from: tuple["Claim", ...] = ()      # parents, for ancestor-taint checks
    fact_key: str | None = None                 # link back into the fact store
    confirms_hypothesis: bool = False           # flatters US
    flatters_user: bool = False                 # flatters MAHMOOD
    meta: dict = field(default_factory=dict)

    @property
    def is_synthetic(self) -> bool:
        return self.synthetic or self.source_tier is SourceTier.SYNTHETIC

    def has_synthetic_ancestor(self) -> bool:
        """Transitive: a claim derived (even indirectly) from synthetic data is
        itself unexportable. Mirrors the store's frozen/transitive taint."""
        seen: set[int] = set()
        stack = list(self.derived_from)
        while stack:
            c = stack.pop()
            if id(c) in seen:
                continue
            seen.add(id(c))
            if c.is_synthetic:
                return True
            stack.extend(c.derived_from)
        return False
