"""PRISMA 2020 flow accounting + protocol-vs-paper outcome-switching check.

Closes the ``review_workflow`` gap (2/3): the comparators that score 3/3 cover the
full search -> screening -> eligibility -> included flow and report it as a PRISMA
diagram. This module computes that flow deterministically from per-record screening
decisions, and adds an outcome-switching check the commercial tools do not surface.

Two capabilities:
  prisma_flow(records)        -> PRISMA 2020 counts with a per-reason exclusion table.
  outcome_switching(p, r)     -> diff of protocol vs reported outcomes; undisclosed
                                 drops are flagged (ITS base rate ~24%, per the
                                 advanced-stats outcome-switching rule).

Honest accounting: counts come only from records the caller marks with a *confirmed*
decision. A record with no full-text decision is "awaiting assessment", never
silently counted as included or excluded — so the flow never overstates inclusions.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

INCLUDE = "include"
EXCLUDE = "exclude"


def prisma_flow(records: list[dict], artifacts_dir: Path | None = None) -> dict:
    """Compute PRISMA 2020 flow counts from screening records.

    Each record may carry:
      duplicate   (bool)            removed before screening
      ta_decision ('include'|'exclude')   title/abstract screen
      ta_reason   (str)             exclusion reason code (if excluded)
      retrieved   (bool)            report sought & retrieved (default True if TA-included)
      ft_decision ('include'|'exclude'|None)   full-text eligibility
      ft_reason   (str)             exclusion reason code (if excluded)

    Returns the staged counts plus exclusion-reason breakdowns. Records without a
    ft_decision are counted as 'awaiting_assessment', never as included/excluded.
    """
    identified = len(records)
    duplicates = sum(1 for r in records if r.get("duplicate"))
    after_dedup = identified - duplicates

    screened = [r for r in records if not r.get("duplicate")]
    ta_excluded = [r for r in screened if r.get("ta_decision") == EXCLUDE]
    ta_included = [r for r in screened if r.get("ta_decision") == INCLUDE]

    # reports sought for retrieval = TA-included; not retrieved if retrieved is False
    sought = ta_included
    not_retrieved = [r for r in sought if r.get("retrieved") is False]
    retrieved = [r for r in sought if r.get("retrieved") is not False]

    ft_assessed = [r for r in retrieved if r.get("ft_decision") in (INCLUDE, EXCLUDE)]
    ft_excluded = [r for r in ft_assessed if r.get("ft_decision") == EXCLUDE]
    included = [r for r in ft_assessed if r.get("ft_decision") == INCLUDE]
    awaiting = [r for r in retrieved if r.get("ft_decision") not in (INCLUDE, EXCLUDE)]

    report = {
        "capability": "review_workflow",
        "standard": "PRISMA 2020",
        "identification": {
            "records_identified": identified,
            "duplicates_removed": duplicates,
            "records_after_dedup": after_dedup,
        },
        "screening": {
            "records_screened": len(screened),
            "records_excluded_title_abstract": len(ta_excluded),
            "ta_exclusion_reasons": dict(Counter(r.get("ta_reason", "unspecified") for r in ta_excluded)),
            "reports_sought": len(sought),
            "reports_not_retrieved": len(not_retrieved),
            "reports_assessed_eligibility": len(ft_assessed),
            "reports_excluded_full_text": len(ft_excluded),
            "ft_exclusion_reasons": dict(Counter(r.get("ft_reason", "unspecified") for r in ft_excluded)),
            "awaiting_assessment": len(awaiting),
        },
        "included": {
            "studies_included": len(included),
        },
        "policy": "records without a confirmed full-text decision are 'awaiting_assessment', never counted as included",
    }
    if artifacts_dir is not None:
        out_dir = artifacts_dir / "evidence"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "prisma.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def _norm_outcome(name: str) -> str:
    return " ".join((name or "").lower().split())


def outcome_switching(protocol_outcomes: list[str], reported_outcomes: list[str],
                      artifacts_dir: Path | None = None) -> dict:
    """Diff a protocol's pre-specified outcomes against the reported outcomes.

    Flags undisclosed *drops* (pre-specified but not reported) as outcome-switching,
    the highest-RoB pattern (per advanced-stats: ~24% of pre-specified outcomes
    silently dropped in ITS; treat undisclosed drops as a reporting-bias signal).
    """
    proto = {_norm_outcome(o): o for o in protocol_outcomes if (o or "").strip()}
    reported = {_norm_outcome(o): o for o in reported_outcomes if (o or "").strip()}
    dropped = [proto[k] for k in proto if k not in reported]
    added = [reported[k] for k in reported if k not in proto]      # newly introduced, not pre-specified
    preserved = [proto[k] for k in proto if k in reported]

    n_proto = len(proto)
    report = {
        "capability": "outcome_switching_check",
        "protocol_outcome_count": n_proto,
        "reported_outcome_count": len(reported),
        "dropped_outcomes": dropped,
        "added_outcomes": added,
        "preserved_outcomes": preserved,
        "dropped_fraction": round(len(dropped) / n_proto, 4) if n_proto else None,
        "switching_flag": bool(dropped or added),
        "interpretation": (
            "undisclosed dropped outcomes are a reporting-bias signal (high RoB); "
            "added outcomes not in the protocol require an explicit justification"
        ),
    }
    if artifacts_dir is not None:
        out_dir = artifacts_dir / "evidence"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "outcome_switching.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
