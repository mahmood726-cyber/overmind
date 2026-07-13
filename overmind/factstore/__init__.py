"""Shared, append-only, provenance-carrying fact store (architecture fix #1).

The failure this closes: twenty agents, twenty private notebooks. A number crosses
a lane boundary and arrives NAKED — its origin, its verification status, and its
real-or-synthetic flag stripped. A synthetic dataset (DTA70) produced a fake TB
figure (Se 85.8 / Sp 97.8, 17 studies) that three lanes picked up and labelled
"provenance-tracked"; it reached the headline slide.

The store makes provenance UNLOSABLE across lane boundaries:
  * one append-only store every lane reads and writes;
  * every fact carries value + source + derivation + verification + panel vote +
    a REAL/SYNTHETIC flag;
  * the synthetic flag is TRANSITIVE — a fact derived from any synthetic input is
    synthetic, forever;
  * consuming an unverified / synthetic / contradicted number FAILS LOUD;
  * two lanes asserting different values for one fact flag BOTH (silence != agreement);
  * a headline that CONFIRMS a hypothesis cannot be verified without cross-family
    adversarial review + a pre-registered refutation criterion (anti-sycophancy).
"""
from overmind.factstore.store import (
    FactStore,
    open_shared,
    Fact,
    Provenance,
    Status,
    FactStoreError,
    NoSuchFactError,
    SyntheticFactError,
    UnverifiedFactError,
    ContradictedFactError,
    SycophancyGateError,
    ImplausibleFactError,
)
from overmind.factstore.plausibility import check_plausibility, PlausibilityResult

__all__ = [
    "FactStore", "open_shared", "Fact", "Provenance", "Status",
    "FactStoreError", "NoSuchFactError", "SyntheticFactError",
    "UnverifiedFactError", "ContradictedFactError", "SycophancyGateError",
    "ImplausibleFactError", "check_plausibility", "PlausibilityResult",
]
