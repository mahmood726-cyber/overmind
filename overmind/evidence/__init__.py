"""Evidence subsystem — the literature-facing half of the research stack.

Overmind's historic strength is *verification* (ma-verify, nma-check, TruthCert):
it checks whether a synthesis is internally coherent. It had no front door to the
literature itself. This package adds that front door — scholarly corpus search,
study screening, structured extraction, citation grounding, and PRISMA workflow
accounting — so the same governance/fail-closed discipline can cover the *inputs*
to a review, not just its outputs.

Design contract (shared by every module here):
  - Offline and deterministic by default. The bundled providers read committed
    fixtures (mirroring Sentinel's out-of-band ``doi-cache.json`` pattern), so the
    nightly verifier and offline e156 dashboards run with no network.
  - Live network access (PubMed/Scholar MCP) is an OPTIONAL, pluggable provider —
    never the default path, and it must declare ``available=False`` when it cannot
    actually reach a backend, so scoring never credits a capability that didn't run.
  - Honest under-claiming: every artifact records its provider, source, and counts.
    The research benchmark credits a capability only when its artifact exists and is
    non-empty.
"""
from __future__ import annotations

from overmind.evidence.corpus import (
    CorpusHit,
    CorpusProvider,
    CorpusRecord,
    CorpusSearch,
    McpCorpusProvider,
    OfflineCorpusProvider,
    default_provider,
    rank,
)
from overmind.evidence.extraction import (
    ExtractionError,
    extract_and_validate,
    js_escape,
    validate_trial,
)
from overmind.evidence.grounding import (
    GroundedClaim,
    extract_identifiers,
    ground_claims,
)
from overmind.evidence.screening import (
    EXCLUSION_REASONS,
    ScreeningProposal,
    ScreeningRun,
    pico_query,
    screen,
)

__all__ = [
    "CorpusHit",
    "CorpusProvider",
    "CorpusRecord",
    "CorpusSearch",
    "McpCorpusProvider",
    "OfflineCorpusProvider",
    "default_provider",
    "rank",
    "EXCLUSION_REASONS",
    "ScreeningProposal",
    "ScreeningRun",
    "pico_query",
    "screen",
    "ExtractionError",
    "extract_and_validate",
    "js_escape",
    "validate_trial",
    "GroundedClaim",
    "extract_identifiers",
    "ground_claims",
]
