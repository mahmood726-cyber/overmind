"""Screening recall calibration — measure the worklist against the 95% safety bar.

The screening module (screening.py) is deliberately conservative and human-gated:
it NEVER auto-includes, it only ranks and SUGGESTS. That is the safe posture the SR
literature supports (LLM screening precision collapses to 0.004-0.096 at realistic
class-imbalance, and no single LLM met the 95%-recall safety bar — best 0.94; Oami
et al. 2024, JAMA Netw Open, DOI 10.1001/jamanetworkopen.2024.20496). But
"never auto-include" is not a recall number.

This module makes the worklist's recall MEASURABLE against a stated threshold: given
a labelled set with gold include/exclude decisions, what fraction of the true
includes does the worklist surface in the buckets a human actually reviews
(SUGGEST_INCLUDE, and SUGGEST_INCLUDE ∪ SUGGEST_UNCLEAR)? It reports recall, the
implied human review burden, and whether the review bucket clears the 0.95 bar — it
does NOT auto-decide. Deterministic, offline, stdlib-only.

Safety bar: 0.95 integrated sensitivity (Oami et al. 2024, JAMA Netw Open, DOI
10.1001/jamanetworkopen.2024.20496; the SR field's recall threshold for screening
to be "safe" to deploy).
"""
from __future__ import annotations

from overmind.evidence.corpus import CorpusRecord
from overmind.evidence.screening import SUGGEST_EXCLUDE, SUGGEST_INCLUDE, SUGGEST_UNCLEAR, screen

SAFETY_BAR = 0.95  # integrated-sensitivity threshold from the SR screening literature


def screening_recall(
    records: list[CorpusRecord],
    gold_includes: list[str],
    query: str | None = None,
    pico: dict | None = None,
    include_threshold: float = 4.0,
    exclude_threshold: float = 0.5,
    safety_bar: float = SAFETY_BAR,
) -> dict:
    """Measure worklist recall against ``gold_includes`` (record_ids the human says
    are true includes). Reports recall for the SUGGEST_INCLUDE bucket and for the
    review bucket (SUGGEST_INCLUDE ∪ SUGGEST_UNCLEAR), vs the safety bar."""
    gold = set(gold_includes)
    if not gold:
        raise ValueError("gold_includes must be non-empty to measure recall")

    # screen() de-dups on record_id internally, so the proposal buckets reflect the unique
    # set. Count candidate_count / workload_fraction over the SAME deduped set, not the raw
    # input, or the denominator is inflated by duplicates the worklist never screened.
    from overmind.evidence.screening import _dedup_by_record_id
    records = _dedup_by_record_id(records)

    proposals = screen(records, query=query, pico=pico,
                       include_threshold=include_threshold, exclude_threshold=exclude_threshold)
    by_sugg: dict[str, set[str]] = {SUGGEST_INCLUDE: set(), SUGGEST_UNCLEAR: set(), SUGGEST_EXCLUDE: set()}
    for p in proposals:
        by_sugg[p.suggestion].add(p.record_id)

    suggest_include = by_sugg[SUGGEST_INCLUDE]
    review_bucket = by_sugg[SUGGEST_INCLUDE] | by_sugg[SUGGEST_UNCLEAR]

    def _recall(bucket: set[str]) -> float:
        return len(gold & bucket) / len(gold)

    def _precision(bucket: set[str]) -> float | None:
        return (len(gold & bucket) / len(bucket)) if bucket else None

    review_recall = _recall(review_bucket)
    n = len(records)
    missed = sorted(gold - review_bucket)  # gold includes a human would NOT see -> the danger set
    return {
        "capability": "screening_recall_calibration",
        "safety_bar": safety_bar,
        "candidate_count": n,
        "gold_include_count": len(gold),
        "include_bucket": {
            "recall": _recall(suggest_include),
            "precision": _precision(suggest_include),
            "size": len(suggest_include),
        },
        "review_bucket": {  # SUGGEST_INCLUDE ∪ SUGGEST_UNCLEAR — what a human screens
            "recall": review_recall,
            "precision": _precision(review_bucket),
            "size": len(review_bucket),
            "workload_fraction": round(len(review_bucket) / n, 4) if n else None,
        },
        "meets_safety_bar": review_recall >= safety_bar,
        "missed_gold_includes": missed,  # empty == no true include hidden from the human
        "policy": (
            "machine never auto-includes; this reports the MEASURED recall of the human "
            f"review bucket against the {safety_bar} safety bar — it does not auto-decide"
        ),
    }
