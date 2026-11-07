"""Gate 1 — the export / render / briefing boundary. F2's real fix.

Ranked #1 by damage prevented and by both external reviewers. Taint that is
*tracked but not enforced* is decoration (the F2 lesson). This is the single
chokepoint every number must pass through before it can appear in a document,
slide, app page, or a message to the user.

FAIL CLOSED. A number is refused unless ALL hold:
  - it is not synthetic and has no synthetic ancestor
  - it declares a real source tier
  - it carries a non-empty locator (where in that source it lives)

Two entry points:
  guard_export(claim)              -- validate a typed Claim
  guard_export_from_store(key, fs) -- validate a fact resolved from the store,
                                      so a fabricated store value (DTA70) is
                                      structurally impossible to export.

The whole point: a naive path `store.get(id).value` returns the raw number with
no guard (that is exactly the pre-fix state). Routing every export through here
is the missing caller.
"""
from __future__ import annotations

import re
from typing import Any

from .contract import Claim, SourceTier


class ExportBlocked(RuntimeError):
    """Raised at the boundary when a number is not fit to leave the harness."""


# A locator must look like a real pointer into a real source. We cannot verify it
# against ground truth here (that is the honest residual — see the closing note in
# HARNESS-SELF-REVIEW), but we CAN reject the obvious spoofs both external
# reviewers named ("FakeLocator-123", "PMID:fake#abstract"). A real locator names
# a recognised identifier AND a field/line within it.
_ID_PATTERNS = (
    r"NCT\d{8}",                 # ClinicalTrials.gov
    r"PMID:\s?\d+",              # PubMed
    r"PMC\d+",                   # PubMed Central
    r"10\.\d{4,9}/\S+",          # DOI
    r"ISRCTN\d+", r"PACTR\d+",   # other registries
)
_ID_RE = re.compile("|".join(_ID_PATTERNS), re.IGNORECASE)
_PLACEHOLDER_RE = re.compile(
    r"fake|placeholder|todo|tbd|xxx|dummy|example|foo|bar|test123|lorem",
    re.IGNORECASE,
)


def _locator_is_real_shaped(locator: str) -> tuple[bool, str]:
    """(ok, reason). Structural, not ground-truth. Requires a recognised id, a
    field/line anchor (# or : with a locator part), and no placeholder token."""
    loc = (locator or "").strip()
    if _PLACEHOLDER_RE.search(loc):
        return False, "locator looks like a placeholder"
    if not _ID_RE.search(loc):
        return False, ("locator names no recognised source id "
                       "(NCT/PMID/PMC/DOI/ISRCTN/PACTR)")
    # A field/line anchor is required so the pointer names WHERE in the source
    # the number lives, not just which document. '#' is the anchor separator
    # (e.g. 'PMID:31234567#abstract', 'NCT01439880#designGroups[0]'). The ':'
    # inside 'PMID:...' is part of the id, not an anchor.
    anchor = loc.split("#", 1)[1] if "#" in loc else ""
    if not anchor.strip():
        return False, "locator has no field/line anchor (need e.g. '#outcome[2]')"
    return True, ""


def guard_export(claim: Claim) -> Claim:
    """Fail closed unless the claim is exportable. Returns the claim on success
    so it can be used inline: ``render(guard_export(claim))``."""
    if not isinstance(claim, Claim):
        raise ExportBlocked(
            f"export boundary only accepts typed Claim objects, got "
            f"{type(claim).__name__!r} — wrap the raw number in a Claim first "
            f"(that forces provenance + locator)."
        )
    if claim.is_synthetic:
        raise ExportBlocked(
            f"BLOCKED: {claim.text!r} is synthetic/fabricated and must never "
            f"cross into a document or a message to the user."
        )
    if claim.has_synthetic_ancestor():
        raise ExportBlocked(
            f"BLOCKED: {claim.text!r} is derived from synthetic data "
            f"(transitive taint) — unexportable."
        )
    if claim.source_tier is None:
        raise ExportBlocked(f"BLOCKED: {claim.text!r} has no source tier.")
    if not (claim.locator or "").strip():
        raise ExportBlocked(
            f"BLOCKED: {claim.text!r} has no locator — a number with no "
            f"pointer to where it lives in its source cannot be exported "
            f"(a PMID/NCT + field/line is required)."
        )
    # DERIVED claims inherit their locators from parents; registry/abstract/OA
    # claims must carry a real-shaped pointer (rejects the fake-locator spoof).
    if claim.source_tier is not SourceTier.DERIVED:
        ok, reason = _locator_is_real_shaped(claim.locator)
        if not ok:
            raise ExportBlocked(
                f"BLOCKED: {claim.text!r} locator {claim.locator!r} — {reason}. "
                f"A plausible-but-fabricated pointer is not a source."
            )
    return claim


def guard_export_from_store(key: str, fs: Any, *, lane: str = "export") -> Any:
    """Resolve ``key`` from a FactStore and fail closed exactly as the boundary
    must. This is the missing caller that connects the store's taint to export.

    Uses the store's own ``consume_verified`` (raises SyntheticFactError /
    UnverifiedFactError / ContradictedFactError / ImplausibleFactError), so a
    fabricated value like the DTA70 Xpert sensitivity cannot be emitted, and a
    lane that merely *read* synthetic data is itself tainted.
    """
    # consume_verified already fails closed on synthetic / unverified /
    # contradicted / implausible. We additionally require a locator, because a
    # "verified" number with no pointer is still not fit for a briefing.
    value = fs.consume_verified(key, lane=lane)  # raises on any taint
    facts = fs.facts_for(key)
    locator = next((f.source_locator for f in facts if f.consumable), "")
    if not (locator or "").strip():
        raise ExportBlocked(
            f"BLOCKED: fact {key!r} is verified but has no source_locator — "
            f"cannot export a number with no pointer to its source."
        )
    return value


def guarded(claims) -> list[Claim]:
    """Guard a batch; fails closed on the FIRST bad claim (no partial exports)."""
    return [guard_export(c) for c in claims]
