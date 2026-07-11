"""Calibrated extraction seam — quorum + conformal abstention + per-cell provenance.

This module sits **above** the deterministic pooling/validation core and never
calls an LLM itself: it *consumes* two independent extractions (from any source —
two LLMs, or two deterministic parsers) and adjudicates them into an auditable
per-cell verdict. The deterministic core (``pooling.py``, ``extraction.py``) is
untouched; this is purely additive.

Three validated methods from the 2026 evidence-extraction literature, as cited by
the task brief:

1. **Consensus-or-flag quorum extraction** — Konet, Gartlehner et al.,
   *JAMIA* 2025 (two heterogeneous models extract each field; agreement is
   accepted, disagreement is *flagged* for cross-critique / human, never silently
   resolved). Implemented in :func:`adjudicate_cell` (states ACCEPT / FLAG_DISAGREE).

2. **Conformal calibrated abstention** — Shrestha & Kim, 2026 (split-conformal
   selective prediction with *per-field-type* rejection thresholds: abstain rather
   than emit a low-confidence value). Implemented in :func:`calibrate_thresholds`
   and :class:`ConformalAbstainer` (state ABSTAIN_LOWCONF). The threshold is fit
   ONLY on a held-out calibration set of correct extractions; the accept-rate on
   test data is an out-of-sample consequence, never tuned on test labels.

3. **Per-cell provenance + ``both_wrong`` abstention** — EviSearch pattern (every
   extracted cell carries its source span + confidence; an explicit
   *both-models-agree-but-fail-an-independent-check* abstain). Implemented via
   :class:`ExtractedValue` (span + confidence) and the BOTH_WRONG state, raised
   when the quorum agrees on a value that an independent ``structural_check``
   rejects — the one failure mode consensus alone cannot catch.

Design invariants:
  * Pure functions + frozen dataclasses; stdlib only; deterministic; no I/O.
  * Model-agnostic: the "two models" are just two :class:`ExtractedValue` inputs.
  * Fail-toward-review: any ambiguity yields FLAG/ABSTAIN/BOTH_WRONG, never a
    silently-emitted value. A missing field is never back-filled with a default.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field as _dc_field
from enum import Enum
from typing import Callable, Optional


class CellState(str, Enum):
    """Adjudicated state of one extracted cell."""

    ACCEPT = "accept"                 # quorum agrees, confident, passes structural check
    FLAG_DISAGREE = "flag_disagree"   # the two extractors disagree -> cross-critique/human
    ABSTAIN_LOWCONF = "abstain_lowconf"  # calibrated confidence below tau -> decline
    BOTH_WRONG = "both_wrong"         # quorum agrees but fails an independent check


# Ratio measures compare on the log scale; differences compare on the natural scale.
_RATIO_FIELD_TYPES = frozenset({"RR", "OR", "HR", "ratio", "rr", "or", "hr"})


@dataclass(frozen=True, slots=True)
class ExtractedValue:
    """One model's extraction of one field, with provenance (EviSearch pattern).

    ``value`` is ``None`` when the model declined / found nothing (a first-class
    "not present", not an error). ``source_span`` is the verbatim text the value
    was read from (auditability); ``confidence`` in [0, 1].
    """

    value: object
    confidence: float = 0.0
    source_span: Optional[str] = None
    model: Optional[str] = None

    def __post_init__(self) -> None:
        if not (0.0 <= float(self.confidence) <= 1.0):
            raise ValueError(f"confidence must be in [0,1], got {self.confidence!r}")


@dataclass(frozen=True, slots=True)
class CellVerdict:
    """Result of adjudicating one field across two extractions."""

    field_type: str
    state: CellState
    value: object                     # the accepted value, else None
    confidence: float
    reason: str
    provenance: tuple = ()            # the two ExtractedValues, for audit

    @property
    def accepted(self) -> bool:
        return self.state is CellState.ACCEPT

    @property
    def needs_review(self) -> bool:
        return self.state in (CellState.FLAG_DISAGREE, CellState.BOTH_WRONG)

    @property
    def abstained(self) -> bool:
        return self.state is CellState.ABSTAIN_LOWCONF

    def to_dict(self) -> dict:
        return {
            "field_type": self.field_type,
            "state": self.state.value,
            "value": self.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "provenance": [
                {"value": p.value, "confidence": p.confidence,
                 "source_span": p.source_span, "model": p.model}
                for p in self.provenance
            ],
        }


def values_agree(a: object, b: object, field_type: str,
                 *, rel_tol: float = 0.05, abs_tol: float = 1e-9) -> bool:
    """Do two extracted values agree for this field type?

    * Both ``None`` -> agree (a shared "not present"; downstream this is an
      agreed abstention, which is *correct* on adversarial "no value" text).
    * One ``None`` -> disagree.
    * Numbers: ratio field types compare on the log scale (a 2x vs 0.5x error is
      symmetric); difference/other numerics compare on relative tolerance.
    * Everything else: case-insensitive string equality.
    """
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if isinstance(a, bool) or isinstance(b, bool):  # bool is-an-int: compare exactly
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        fa, fb = float(a), float(b)
        if not (math.isfinite(fa) and math.isfinite(fb)):
            return fa == fb
        if field_type in _RATIO_FIELD_TYPES:
            if fa <= 0 or fb <= 0:            # non-positive ratio: cannot log-compare
                return abs(fa - fb) <= abs_tol
            return abs(math.log(fa) - math.log(fb)) <= rel_tol
        return abs(fa - fb) <= abs_tol + rel_tol * max(abs(fa), abs(fb))
    return str(a).strip().lower() == str(b).strip().lower()


def adjudicate_cell(field_type: str, ext_a: ExtractedValue, ext_b: ExtractedValue,
                    *, threshold: float = 0.0,
                    structural_check: Optional[Callable[[object], bool]] = None,
                    rel_tol: float = 0.05) -> CellVerdict:
    """Adjudicate one field from two independent extractions.

    Order of checks (fail-toward-review):
      1. **Disagree** -> FLAG_DISAGREE (consensus-or-flag; Konet/Gartlehner 2025).
      2. Agree on ``None`` -> ABSTAIN_LOWCONF (agreed "not present"; correct
         abstention on no-value text).
      3. Agree on a value that fails ``structural_check`` -> BOTH_WRONG (EviSearch:
         the two-optimists-agreeing failure mode).
      4. Agree, passes structural, but calibrated confidence < ``threshold``
         -> ABSTAIN_LOWCONF (conformal selective prediction; Shrestha & Kim 2026).
      5. Otherwise -> ACCEPT.

    ``threshold`` is the per-field-type tau from :func:`calibrate_thresholds`
    (default 0.0 = accept-if-agree, i.e. quorum only). Confidence of an agreed
    cell is the min of the two models' confidences (weakest-link).
    """
    prov = (ext_a, ext_b)
    if not values_agree(ext_a.value, ext_b.value, field_type, rel_tol=rel_tol):
        return CellVerdict(field_type, CellState.FLAG_DISAGREE, None,
                           min(ext_a.confidence, ext_b.confidence),
                           f"extractors disagree: {ext_a.value!r} vs {ext_b.value!r}", prov)

    agreed = ext_a.value  # both agree; pick either (they are equal within tol)
    conf = min(ext_a.confidence, ext_b.confidence)

    if agreed is None:
        return CellVerdict(field_type, CellState.ABSTAIN_LOWCONF, None, conf,
                           "both extractors declined (no value present)", prov)

    if structural_check is not None:
        try:
            ok = bool(structural_check(agreed))
        except Exception as exc:  # noqa: BLE001 - a raising check means "reject"
            ok = False
            return CellVerdict(field_type, CellState.BOTH_WRONG, None, conf,
                               f"agreed value {agreed!r} failed structural check ({exc})", prov)
        if not ok:
            return CellVerdict(field_type, CellState.BOTH_WRONG, None, conf,
                               f"agreed value {agreed!r} rejected by independent structural check", prov)

    if conf < threshold:
        return CellVerdict(field_type, CellState.ABSTAIN_LOWCONF, None, conf,
                           f"confidence {conf:.3f} < calibrated tau {threshold:.3f}", prov)

    return CellVerdict(field_type, CellState.ACCEPT, agreed, conf,
                       "quorum agreement, confident, passed structural check", prov)


# --------------------------------------------------------------------------- #
# Conformal calibrated abstention (split-conformal selective prediction).
# --------------------------------------------------------------------------- #

@dataclass(frozen=True, slots=True)
class CalibrationExample:
    """One labelled calibration point: an extracted value, its confidence, whether
    it was actually CORRECT, and its field type."""

    field_type: str
    confidence: float
    correct: bool


def calibrate_thresholds(examples: list[CalibrationExample], *, alpha: float = 0.1,
                         default_tau: float = 0.0) -> dict[str, float]:
    """Per-field-type conformal thresholds via split-conformal quantiles.

    For each field type we take the confidences of the **correct** calibration
    extractions and set ``tau`` = their empirical ``alpha``-quantile. Accepting
    only cells with ``confidence >= tau`` then retains ``>= (1 - alpha)`` of true
    extractions *on the calibration distribution* — a coverage guarantee whose
    test-time accept-rate is out-of-sample (never tuned on test labels).

    ``alpha`` is the tolerated loss of true extractions (the rejection budget for
    good cells), pinned before the run. Field types with no correct calibration
    example fall back to ``default_tau`` (accept-if-agree).
    """
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be in (0,1), got {alpha}")
    by_type: dict[str, list[float]] = {}
    for ex in examples:
        if ex.correct:
            by_type.setdefault(ex.field_type, []).append(float(ex.confidence))
    thresholds: dict[str, float] = {}
    for ftype, confs in by_type.items():
        confs.sort()
        # alpha-quantile (lower): index = floor(alpha * n), clamped. Retains
        # (1-alpha) of correct examples at-or-above tau.
        n = len(confs)
        idx = min(n - 1, max(0, int(math.floor(alpha * n))))
        thresholds[ftype] = confs[idx]
    thresholds.setdefault("__default__", default_tau)
    return thresholds


@dataclass(slots=True)
class ConformalAbstainer:
    """Applies calibrated per-field-type thresholds and reports coverage/rejection."""

    thresholds: dict[str, float]

    def tau_for(self, field_type: str) -> float:
        return self.thresholds.get(field_type, self.thresholds.get("__default__", 0.0))

    def accept(self, field_type: str, confidence: float) -> bool:
        return confidence >= self.tau_for(field_type)

    def report(self, examples: list[CalibrationExample]) -> dict:
        """Measure coverage vs rejection on a (test) set of labelled examples.

        * coverage       = accepted-and-correct / all-correct  (recall of true cells)
        * rejection_rate = abstained / all
        * accepted_error = accepted-and-wrong / accepted       (empirical risk kept)
        """
        n = len(examples)
        n_correct = sum(1 for e in examples if e.correct)
        accepted = [e for e in examples if self.accept(e.field_type, e.confidence)]
        acc_correct = sum(1 for e in accepted if e.correct)
        acc_wrong = sum(1 for e in accepted if not e.correct)
        return {
            "n": n,
            "n_correct": n_correct,
            "accepted": len(accepted),
            "rejection_rate": (n - len(accepted)) / n if n else None,
            "coverage": acc_correct / n_correct if n_correct else None,
            "accepted_error": acc_wrong / len(accepted) if accepted else None,
            "thresholds": dict(self.thresholds),
        }


# --------------------------------------------------------------------------- #
# Record-level rollup.
# --------------------------------------------------------------------------- #

def adjudicate_record(fields: dict[str, tuple[ExtractedValue, ExtractedValue]],
                      *, abstainer: Optional[ConformalAbstainer] = None,
                      structural_checks: Optional[dict[str, Callable[[object], bool]]] = None,
                      rel_tol: float = 0.05) -> dict:
    """Adjudicate a whole record: ``{field_type: (ext_a, ext_b)}`` -> per-cell
    verdicts + a rollup. ``needs_review`` is True if any cell is FLAG/BOTH_WRONG.
    Purely additive; the accepted values are exactly the deterministic-core input."""
    structural_checks = structural_checks or {}
    cells: dict[str, CellVerdict] = {}
    for ftype, (a, b) in fields.items():
        tau = abstainer.tau_for(ftype) if abstainer else 0.0
        v = adjudicate_cell(ftype, a, b, threshold=tau,
                            structural_check=structural_checks.get(ftype), rel_tol=rel_tol)
        cells[ftype] = v
    accepted = {f: v.value for f, v in cells.items() if v.accepted}
    return {
        "cells": {f: v.to_dict() for f, v in cells.items()},
        "accepted": accepted,
        "flagged": [f for f, v in cells.items() if v.state is CellState.FLAG_DISAGREE],
        "both_wrong": [f for f, v in cells.items() if v.state is CellState.BOTH_WRONG],
        "abstained": [f for f, v in cells.items() if v.abstained],
        "needs_review": any(v.needs_review for v in cells.values()),
    }
