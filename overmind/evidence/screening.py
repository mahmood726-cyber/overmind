"""Study screening — offline, conservative, human-gated.

Closes part of the ``screening_extraction`` benchmark gap. This is the offline,
deterministic complement to RapidMeta's browser screening UI: given a candidate
corpus and PICO criteria, it produces a *ranked screening worklist* with a
suggested action and an exclusion-reason code — but the authoritative decision
stays ``pending`` / ``needsReview`` until a human confirms.

Why it never auto-includes (RapidMeta lessons, hard-won):
  - v9.2: an "auto-detect RCT" classifier over-aggressively marked registry trials
    ``include``; the fix reverted them to manual review. So this module SUGGESTS
    but never sets ``include``.
  - Per the substitution-on-missing lesson, we never fabricate a decision; absence
    of a strong signal yields ``pending``, not a guess.

Ranking reuses :func:`overmind.evidence.corpus.rank` (BM25) so screening relevance
and corpus search share one retrieval function. Active-learning-lite: if the caller
supplies seed includes (record_ids already judged relevant), their distinctive
terms are folded into the query (Rocchio-style relevance feedback), deterministically.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from overmind.evidence.corpus import CorpusRecord, rank, tokenize

# Screening decision vocabulary — matches RapidMeta's trial ``status`` field.
SEARCH = "search"
INCLUDE = "include"
EXCLUDE = "exclude"
PENDING = "pending"
DECISIONS = frozenset({SEARCH, INCLUDE, EXCLUDE, PENDING})

# Suggestion (advisory only) — distinct from the authoritative decision.
SUGGEST_INCLUDE = "suggest_include"
SUGGEST_EXCLUDE = "suggest_exclude"
SUGGEST_UNCLEAR = "suggest_unclear"

# Controlled exclusion-reason taxonomy. A free-text reason is allowed too, but the
# code must come from here so reasons aggregate cleanly into a PRISMA exclusion table.
EXCLUSION_REASONS = frozenset({
    "wrong_population",
    "wrong_intervention",
    "wrong_comparator",
    "wrong_outcome",
    "wrong_design",
    "not_primary_study",
    "duplicate",
    "no_outcome_data",
    "language",
})


@dataclass(frozen=True, slots=True)
class ScreeningProposal:
    """One ranked screening suggestion. ``decision`` is deliberately ``pending``
    and ``needs_review`` True: a machine never closes a screening decision."""

    record_id: str
    score: float
    rank: int
    suggestion: str               # SUGGEST_* — advisory
    decision: str = PENDING       # authoritative status; stays PENDING here
    needs_review: bool = True
    matched_terms: list[str] = field(default_factory=list)
    title: str = ""

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "score": round(self.score, 4),
            "rank": self.rank,
            "suggestion": self.suggestion,
            "decision": self.decision,
            "needs_review": self.needs_review,
            "matched_terms": list(self.matched_terms),
            "title": self.title,
        }


def pico_query(pico: dict) -> str:
    """Flatten a RapidMeta-style pico dict ({pop,int,comp,out,subgroup}) into a
    screening query string. Missing keys are skipped (no fabricated text)."""
    parts = [pico.get(k, "") for k in ("pop", "int", "comp", "out", "subgroup")]
    query = " ".join(p for p in parts if (p or "").strip())
    if not query.strip():
        raise ValueError("pico produced an empty query — need at least one of pop/int/comp/out")
    return query


def _dedup_by_record_id(records: list[CorpusRecord]) -> list[CorpusRecord]:
    """Drop records that repeat an already-seen record_id (first occurrence wins),
    matching OfflineCorpusProvider's contract. Without this, a caller passing a raw
    list with two records sharing a record_id (only one of which scores in BM25)
    would have the zero-score copy silently suppressed by the completeness loop,
    making proposal_count < candidate_count — a silent truncation. Deduping up front
    makes record_id the unit and keeps proposal_count == (deduped) candidate_count."""
    seen: set[str] = set()
    out: list[CorpusRecord] = []
    for rec in records:
        if rec.record_id in seen:
            continue
        seen.add(rec.record_id)
        out.append(rec)
    return out


def _relevance_feedback_terms(records: list[CorpusRecord], seed_ids: list[str], top_n: int = 8) -> list[str]:
    """Rocchio-lite: the most frequent non-trivial terms across seed includes."""
    by_id = {r.record_id: r for r in records}
    counter: Counter[str] = Counter()
    for rid in seed_ids:
        rec = by_id.get(rid)
        if rec is None:
            continue
        counter.update(set(tokenize(rec.searchable_text)))
    # require a term to appear in >1 seed when there are multiple seeds, to avoid
    # latching onto one document's idiosyncratic vocabulary
    floor = 2 if len([r for r in seed_ids if r in by_id]) > 1 else 1
    terms = sorted((t for t, c in counter.items() if c >= floor and len(t) > 2),
                   key=lambda t: (-counter[t], t))
    return terms[:top_n]


def screen(
    records: list[CorpusRecord],
    query: str | None = None,
    pico: dict | None = None,
    seed_includes: list[str] | None = None,
    include_threshold: float = 4.0,
    exclude_threshold: float = 0.5,
    limit: int | None = None,
) -> list[ScreeningProposal]:
    """Rank ``records`` for relevance and emit conservative screening proposals.

    ``query`` or ``pico`` must be given (pico is flattened via :func:`pico_query`).
    ``seed_includes`` (record_ids judged relevant) drive relevance feedback.

    Thresholds map BM25 score → advisory suggestion only:
      score >= include_threshold -> SUGGEST_INCLUDE
      score <= exclude_threshold -> SUGGEST_EXCLUDE
      otherwise                  -> SUGGEST_UNCLEAR
    The authoritative ``decision`` is always PENDING with needs_review=True.
    """
    if not query and not pico:
        raise ValueError("screen() needs either query or pico")
    records = _dedup_by_record_id(records)  # record_id is the unit; no silent dup suppression
    effective_query = query or pico_query(pico)
    if seed_includes:
        fb = _relevance_feedback_terms(records, seed_includes)
        if fb:
            effective_query = effective_query + " " + " ".join(fb)

    hits = rank(records, effective_query, limit=limit or len(records))
    hit_ids = {h.record.record_id for h in hits}

    proposals: list[ScreeningProposal] = []
    for i, hit in enumerate(hits, start=1):
        if hit.score >= include_threshold:
            suggestion = SUGGEST_INCLUDE
        elif hit.score <= exclude_threshold:
            suggestion = SUGGEST_EXCLUDE
        else:
            suggestion = SUGGEST_UNCLEAR
        proposals.append(ScreeningProposal(
            record_id=hit.record.record_id,
            score=hit.score,
            rank=i,
            suggestion=suggestion,
            matched_terms=hit.matched_terms,
            title=hit.record.title,
        ))

    # records with zero lexical overlap never appear in `hits`; surface them as
    # explicit SUGGEST_EXCLUDE/PENDING so the screening set is complete, not silently
    # truncated (no-silent-caps rule).
    next_rank = len(proposals) + 1
    for rec in records:
        if rec.record_id in hit_ids:
            continue
        proposals.append(ScreeningProposal(
            record_id=rec.record_id,
            score=0.0,
            rank=next_rank,
            suggestion=SUGGEST_EXCLUDE,
            matched_terms=[],
            title=rec.title,
        ))
        next_rank += 1
    return proposals


@dataclass(frozen=True, slots=True)
class ScreeningRun:
    provider_records: list[CorpusRecord]
    artifacts_dir: Path | None = None

    def run(self, query: str | None = None, pico: dict | None = None,
            seed_includes: list[str] | None = None, **kwargs) -> dict:
        # Dedup on record_id up front so candidate_count reflects the unique set that
        # screen() actually worklist-s; surface the removed count rather than letting
        # it vanish silently (no-silent-caps rule).
        deduped = _dedup_by_record_id(self.provider_records)
        proposals = screen(deduped, query=query, pico=pico,
                           seed_includes=seed_includes, **kwargs)
        counts = Counter(p.suggestion for p in proposals)
        report = {
            "capability": "screening",
            "query": query or (pico_query(pico) if pico else None),
            "used_relevance_feedback": bool(seed_includes),
            "candidate_count": len(deduped),
            "duplicates_removed": len(self.provider_records) - len(deduped),
            "proposal_count": len(proposals),
            "suggestion_counts": dict(counts),
            # every proposal is pending/needs_review — the machine closes nothing
            "auto_included": 0,
            "decision_policy": "machine suggests; human confirms (all decisions PENDING/needs_review)",
            "exclusion_reason_vocab": sorted(EXCLUSION_REASONS),
            "proposals": [p.to_dict() for p in proposals],
        }
        if self.artifacts_dir is not None:
            out_dir = self.artifacts_dir / "evidence"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "screening.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        return report
