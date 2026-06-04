"""Structured data extraction — RapidMeta-compatible contract, fail-closed.

Closes the rest of the ``screening_extraction`` gap. This is NOT an LLM extractor;
it is the offline *contract validator* for extracted per-study data, using the
exact field names RapidMeta dashboards consume, so Overmind-validated extractions
drop straight into a RapidMeta config.

Two error tiers (mirrors ma_verify's hard/informative split and RapidMeta's
needsReview gate):
  HARD (raise ExtractionError) — the record is unusable:
    * missing id (nct/pmid) or name
    * no outcomes, or an outcome carrying none of {binary 2x2, ratio+CI, continuous}
    * estimandType outside the controlled vocab
    * rob present but not a 5-element D1-D5 array of valid levels
  SOFT (collected as issues; record marked needs_review=True) — surfaced for a human:
    * CI not ordered (lci <= point <= uci)
    * publishedHR direction contradicts the count-derived OR  (inverted-HR anti-pattern)
    * implausible counts / non-positive ratio / non-positive SE

Per the substitution-on-missing lesson, a missing REQUIRED field is NEVER filled
with a plausible default — it raises with an expected-vs-received message. Auto-
extracted records are always marked needs_review=True (RapidMeta v11.2 gate).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

# Effect-measure vocabulary (RapidMeta estimandType).
ESTIMAND_TYPES = frozenset({"RR", "HR", "OR", "MD", "RD"})
RATIO_MEASURES = frozenset({"RR", "HR", "OR"})  # null effect = 1
DIFF_MEASURES = frozenset({"MD", "RD"})         # null effect = 0

ROB_LEVELS = frozenset({"low", "some-concerns", "high"})
ROB_DOMAINS = 5  # RoB 2.0 D1-D5

_RATIO_NULL = 1.0


class ExtractionError(ValueError):
    """A hard contract violation — the extracted record cannot be used."""


def js_escape(value: str) -> str:
    """Escape a string for safe embedding in a single-quoted JS literal.

    Reused from RapidMeta's clone.py — an unescaped apostrophe inside ``out: '...'``
    terminated the string and broke 27 dashboards (see lessons.md). Provided here so
    Overmind-validated text is safe to stamp into a RapidMeta config without re-
    learning that bug.
    """
    return (value or "").replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")


def _num(value):
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _classify_outcome(outcome: dict) -> str:
    """Return 'binary' | 'ratio' | 'continuous' for a valid outcome, else raise."""
    tE, tN = _num(outcome.get("tE")), _num(outcome.get("tN"))
    cE, cN = _num(outcome.get("cE")), _num(outcome.get("cN"))
    effect = _num(outcome.get("effect"))
    if effect is None:
        effect = _num(outcome.get("publishedHR"))
    lci = _num(outcome.get("lci")) if outcome.get("lci") is not None else _num(outcome.get("hrLCI"))
    uci = _num(outcome.get("uci")) if outcome.get("uci") is not None else _num(outcome.get("hrUCI"))
    md, se = _num(outcome.get("md")), _num(outcome.get("se"))

    has_binary = None not in (tE, tN, cE, cN)
    has_ratio = effect is not None and lci is not None and uci is not None
    has_continuous = md is not None and se is not None

    if has_binary:
        return "binary"
    if has_ratio:
        return "ratio"
    if has_continuous:
        return "continuous"
    raise ExtractionError(
        f"outcome {outcome.get('shortLabel') or outcome.get('title') or '?'!r} carries no usable "
        "data: need binary (tE,tN,cE,cN) OR ratio (effect/publishedHR + lci/uci) OR continuous (md,se)"
    )


def _check_outcome_coherence(outcome: dict, kind: str) -> list[str]:
    """SOFT checks. Returns human-readable issue strings (never raises).

    Checks run on whichever representation is *present*, not on a single winning
    ``kind`` — an outcome may carry both 2x2 counts and a published ratio, and the
    inverted-HR check specifically needs both at once.
    """
    issues: list[str] = []
    estimand = outcome.get("estimandType")

    tE, tN = _num(outcome.get("tE")), _num(outcome.get("tN"))
    cE, cN = _num(outcome.get("cE")), _num(outcome.get("cN"))
    effect = _num(outcome.get("effect"))
    if effect is None:
        effect = _num(outcome.get("publishedHR"))
    lci = _num(outcome.get("lci")) if outcome.get("lci") is not None else _num(outcome.get("hrLCI"))
    uci = _num(outcome.get("uci")) if outcome.get("uci") is not None else _num(outcome.get("hrUCI"))
    se = _num(outcome.get("se"))

    has_binary = None not in (tE, tN, cE, cN)
    has_ratio = effect is not None

    if has_binary:
        for name, e, nn in (("treatment", tE, tN), ("control", cE, cN)):
            if nn is not None and nn <= 0:
                issues.append(f"{name} arm total {nn} is not positive")
            if e is not None and nn is not None and not (0 <= e <= nn):
                issues.append(f"{name} events {e} outside [0, {nn}]")

    if has_ratio:
        if effect <= 0:
            issues.append(f"ratio effect {effect} is not positive (ratios must be > 0)")
        if None not in (lci, uci) and not (lci <= effect <= uci):
            issues.append(f"CI not ordered: lci={lci} <= effect={effect} <= uci={uci} fails")

    # Direction-disagreement check: a published ratio and the count-derived OR on
    # opposite sides of the null (RapidMeta AUDIT line 14). Needs both representations
    # present, regardless of `kind`. NOTE this is a heuristic, not proof of inversion:
    # the published effect is often an HR while the count-derived value is an OR, and
    # in a high-event-rate / time-varying-hazard regime an HR and an OR can legitimately
    # straddle 1.0 without any data-entry error — so the message reports a *disagreement*
    # to review, not a confirmed mis-label. (Zero-cell 2x2s are skipped here; the
    # advanced-stats 0.5 continuity correction would be needed to extend this safely.)
    if has_binary and has_ratio and tN > 0 and cN > 0:
        a, b = tE, tN - tE
        c, d = cE, cN - cE
        if min(a, b, c, d) >= 0 and a > 0 and b > 0 and c > 0 and d > 0:
            count_or = (a * d) / (b * c)
            if (effect - _RATIO_NULL) * (count_or - _RATIO_NULL) < 0:
                issues.append(
                    f"publishedHR/effect {effect} contradicts count-derived OR {count_or:.3f} "
                    "(opposite sides of 1.0) - review for inversion/mis-label, or a legitimate "
                    "HR-vs-OR divergence under high event rates"
                )

    if se is not None and se <= 0:
        issues.append(f"standard error {se} is not positive")

    if estimand is not None:
        if (has_binary or has_ratio) and estimand in DIFF_MEASURES:
            issues.append(f"estimandType {estimand!r} (a difference) on a ratio/binary outcome")
        if kind == "continuous" and not has_binary and not has_ratio and estimand in RATIO_MEASURES:
            issues.append(f"estimandType {estimand!r} (a ratio) on a continuous outcome")
    return issues


def validate_trial(trial: dict, auto_extracted: bool = False) -> dict:
    """Validate one extracted trial against the RapidMeta contract.

    Returns a normalized dict with ``_issues`` (SOFT findings) and ``needsReview``.
    Raises :class:`ExtractionError` on any HARD violation. Never invents defaults.
    """
    if not isinstance(trial, dict):
        raise ExtractionError(f"trial must be a dict, got {type(trial).__name__}")

    tid = (trial.get("nct") or trial.get("id") or "").strip() or (trial.get("pmid") or "").strip()
    if not tid:
        raise ExtractionError("trial missing required identifier (expected one of: nct, id, pmid)")
    name = (trial.get("name") or "").strip()
    if not name:
        raise ExtractionError(f"trial {tid!r} missing required field 'name' (no default substituted)")

    outcomes = trial.get("allOutcomes") or trial.get("outcomes") or []
    if not isinstance(outcomes, list) or not outcomes:
        raise ExtractionError(f"trial {tid!r} has no outcomes (need >=1 in allOutcomes/outcomes)")

    issues: list[str] = []
    normalized_outcomes = []
    for idx, outcome in enumerate(outcomes):
        if not isinstance(outcome, dict):
            raise ExtractionError(f"trial {tid!r} outcome[{idx}] is not an object")
        estimand = outcome.get("estimandType")
        if estimand is not None and estimand not in ESTIMAND_TYPES:
            raise ExtractionError(
                f"trial {tid!r} outcome[{idx}] estimandType {estimand!r} not in {sorted(ESTIMAND_TYPES)}"
            )
        kind = _classify_outcome(outcome)  # raises if no usable data
        o_issues = _check_outcome_coherence(outcome, kind)
        issues.extend(f"outcome[{idx}] ({outcome.get('shortLabel') or kind}): {m}" for m in o_issues)
        normalized_outcomes.append({**outcome, "_kind": kind})

    rob = trial.get("rob")
    if rob is not None:
        if not isinstance(rob, list) or len(rob) != ROB_DOMAINS:
            raise ExtractionError(
                f"trial {tid!r} rob must be a {ROB_DOMAINS}-element D1-D5 array, got {rob!r}"
            )
        bad = [d for d in rob if d not in ROB_LEVELS]
        if bad:
            raise ExtractionError(f"trial {tid!r} rob has invalid level(s) {bad}; allowed {sorted(ROB_LEVELS)}")

    needs_review = bool(auto_extracted or issues)
    return {
        "id": tid,
        "name": name,
        "source": trial.get("source", "manual"),
        "verified": bool(trial.get("verified", False)),
        "needsReview": needs_review,
        "outcomes": normalized_outcomes,
        "rob": rob,
        "_issues": issues,
    }


def extract_and_validate(trials: list[dict], auto_extracted: bool = False,
                         artifacts_dir: Path | None = None) -> dict:
    """Validate a batch of trials. Hard violations are collected per-trial (the
    batch does not abort), so one bad record never hides the rest."""
    validated, rejected = [], []
    for trial in trials:
        try:
            validated.append(validate_trial(trial, auto_extracted=auto_extracted))
        except ExtractionError as exc:
            rejected.append({"trial": trial.get("nct") or trial.get("id") or trial.get("name"),
                             "error": str(exc)})
    flagged = [v for v in validated if v["needsReview"]]
    report = {
        "capability": "data_extraction",
        "schema": "rapidmeta-compatible (tE/tN/cE/cN | effect/lci/uci | md/se; estimandType; rob[5])",
        "input_count": len(trials),
        "validated_count": len(validated),
        "rejected_count": len(rejected),
        "needs_review_count": len(flagged),
        "auto_extracted": bool(auto_extracted),
        "rejected": rejected,
        "needs_review": [{"id": v["id"], "issues": v["_issues"]} for v in flagged],
        "fail_closed_policy": "missing required field raises; no plausible default is ever substituted",
    }
    if artifacts_dir is not None:
        out_dir = artifacts_dir / "evidence"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "extraction.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    return report
