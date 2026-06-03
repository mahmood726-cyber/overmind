"""Citation grounding — tie every claim to a resolvable source record.

Closes the ``citation_grounding`` benchmark gap (2/3). The comparators that score
3/3 (Elicit sentence-level citations, Scite Smart Citations, Consensus) all share
one property: each output claim is bound to a specific source. This module makes
that binding *auditable and fail-closed* for Overmind: it resolves each claim's
cited identifier (DOI / PMID / NCT / corpus record_id) against the actual corpus
and reports a grounding ratio plus the exact unresolved claims.

It reuses RapidMeta's ``evidence[].source`` provenance idea: a claim carries a
``source`` (a bare identifier string, or a dict with doi/pmid/nct/record_id). A
claim with no identifier is UNGROUNDED — that is the failure this catches, the
same family Sentinel's citation_cascade/citation_resolution rules guard at the
document level. Here we additionally require the identifier to point at a record
that actually exists in the corpus (resolution, not just shape).

Offline and deterministic: it resolves against the in-memory corpus index, makes
no network call. Honest under-claiming: a claim whose identifier is well-formed
but absent from the corpus is reported ``unresolved``, never silently counted as
grounded.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from overmind.evidence.corpus import CorpusRecord

# Identifier extraction (local, offline). DOI shape mirrors Sentinel's VALID_DOI_RE.
_DOI_RE = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)
_PMID_RE = re.compile(r"\bPMID[:=]?\s*(\d{1,9})\b", re.IGNORECASE)
_NCT_RE = re.compile(r"\bNCT\d{8}\b", re.IGNORECASE)


def _norm_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    return doi.strip().rstrip(".,)];\"'").lower() or None


def extract_identifiers(text: str) -> dict:
    """Pull DOI / PMID / NCT identifiers out of free claim text. Returns the first
    of each kind found (claims should cite a single primary source)."""
    doi = _DOI_RE.search(text or "")
    pmid = _PMID_RE.search(text or "")
    nct = _NCT_RE.search(text or "")
    return {
        "doi": _norm_doi(doi.group(0)) if doi else None,
        "pmid": pmid.group(1) if pmid else None,
        "nct": nct.group(0).upper() if nct else None,
    }


@dataclass(frozen=True, slots=True)
class _CorpusIndex:
    by_record_id: dict[str, CorpusRecord]
    by_pmid: dict[str, CorpusRecord]
    by_doi: dict[str, CorpusRecord]

    @classmethod
    def build(cls, records: list[CorpusRecord]) -> "_CorpusIndex":
        by_id, by_pmid, by_doi = {}, {}, {}
        for rec in records:
            by_id[rec.record_id] = rec
            if rec.pmid:
                by_pmid[str(rec.pmid)] = rec
            nd = _norm_doi(rec.doi)
            if nd:
                by_doi[nd] = rec
        return cls(by_id, by_pmid, by_doi)

    def resolve(self, ident: dict) -> CorpusRecord | None:
        if ident.get("record_id") and ident["record_id"] in self.by_record_id:
            return self.by_record_id[ident["record_id"]]
        if ident.get("pmid") and str(ident["pmid"]) in self.by_pmid:
            return self.by_pmid[str(ident["pmid"])]
        nd = _norm_doi(ident.get("doi"))
        if nd and nd in self.by_doi:
            return self.by_doi[nd]
        return None


@dataclass(frozen=True, slots=True)
class GroundedClaim:
    claim_id: str
    text: str
    resolved: bool
    matched_record_id: str | None
    identifier: dict
    reason: str  # why it is/ isn't grounded

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "text": self.text[:200],
            "resolved": self.resolved,
            "matched_record_id": self.matched_record_id,
            "identifier": self.identifier,
            "reason": self.reason,
        }


def _claim_identifier(claim: dict) -> dict:
    """Pull an identifier from a claim. ``source`` may be a dict
    {doi/pmid/nct/record_id} or a bare string; if absent, fall back to scanning
    the claim text. Returns {} when nothing citable is present."""
    src = claim.get("source")
    ident: dict = {}
    if isinstance(src, dict):
        ident = {k: src.get(k) for k in ("doi", "pmid", "nct", "record_id") if src.get(k)}
    elif isinstance(src, str) and src.strip():
        if src.startswith(("pmid:", "doi:")) or src.startswith("NCT"):
            ident["record_id"] = src.strip()
        else:
            ident.update({k: v for k, v in extract_identifiers(src).items() if v})
    if not ident:
        ident = {k: v for k, v in extract_identifiers(claim.get("text", "")).items() if v}
    return ident


def ground_claims(claims: list[dict], records: list[CorpusRecord],
                  artifacts_dir: Path | None = None) -> dict:
    """Resolve each claim's citation against the corpus. Returns a grounding report.

    Each claim: {claim_id, text, source?}. ``source`` is an identifier (string or
    dict) per RapidMeta's evidence[].source convention. A claim with no resolvable
    identifier is reported ungrounded — never silently passed.
    """
    index = _CorpusIndex.build(records)
    grounded: list[GroundedClaim] = []
    for i, claim in enumerate(claims):
        cid = str(claim.get("claim_id") or f"claim-{i}")
        text = claim.get("text", "")
        ident = _claim_identifier(claim)
        if not ident:
            grounded.append(GroundedClaim(cid, text, False, None, {},
                                          "no citation identifier (doi/pmid/nct/record_id) present"))
            continue
        rec = index.resolve(ident)
        if rec is None:
            grounded.append(GroundedClaim(cid, text, False, None, ident,
                                          "identifier present but does not resolve to any corpus record"))
        else:
            grounded.append(GroundedClaim(cid, text, True, rec.record_id, ident, "resolved"))

    total = len(grounded)
    resolved = sum(1 for g in grounded if g.resolved)
    report = {
        "capability": "citation_grounding",
        "corpus_size": len(records),
        "claim_count": total,
        "grounded_count": resolved,
        "ungrounded_count": total - resolved,
        # ratio is None (not 1.0) for an empty claim set — undefined, not perfect.
        "grounding_ratio": round(resolved / total, 4) if total else None,
        "ungrounded": [g.to_dict() for g in grounded if not g.resolved],
        "claims": [g.to_dict() for g in grounded],
        "policy": "a claim with no resolvable doi/pmid/nct/record_id is UNGROUNDED, never assumed",
    }
    if artifacts_dir is not None:
        out_dir = artifacts_dir / "evidence"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "citation_grounding.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    return report
