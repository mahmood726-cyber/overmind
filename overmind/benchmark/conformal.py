"""Conformal accept/abstain gate for the review panel (PV-B, gap-analysis close #2).

Motivation (from the 2026-07-06 held-out gap analysis): Arm C's whole NOT_PROVEN
verdict rests on ONE regression — its false-alarm rate (6/13 = 0.462, the worst of
the three arms). Every one of those 6 false alarms is a *borderline* flag: the
reviewer objects to the artifact's **statistics** rather than identifying a defect —
either

  * the artifact's own 95% CI includes 1.0 ("non-significant, so the stated
    direction is contradicted"), or
  * all studies are zero-event so the pooled RR is *not estimable* ("undefined,
    so the conclusion is unsupported").

On a genuinely-clean artifact these are crying wolf: the model is raising a
*defensible statistical objection to degenerate/hedged data* and being scored as a
false alarm. The right posture on such an input is to **abstain** — decline to
judge — not to flag.

This module is that gate. It converts a reviewer-driven flag into an *abstention*
when the flag's confidence is below a calibrated threshold. An abstained verdict
is neither a flag (so it is not a false alarm on a clean task) nor an acceptance
(so it does not inflate agreement-soundness). The deterministic **witness floor is
never abstained** — an arithmetically-detectable defect always flags.

Design — split-conformal, blinding-preserving
---------------------------------------------
``flag_confidence(reviewer_verdicts)`` scores a panel's flag in [0, 1] from pinned
features: LOW when the flag rests *only* on a significance / degeneracy objection
(``sig-only``) and a single vendor dissents; HIGH when a reviewer cites a concrete
**structural** defect (mislabel, comparator swap, missing null arm, method /
heterogeneity mismatch, subgroup mismatch, impossible cell, transposed CI,
reproduction mismatch) or multiple distinct vendors corroborate.

``calibrate_threshold(defect_confidences, alpha)`` returns ``tau`` = the largest
threshold that RETAINS ``>= (1 - alpha)`` of TRUE-DEFECT flags. **Only the defect
class sets tau** — the clean-task false-alarm reduction is an *out-of-sample*
consequence, never tuned on the clean labels. ``alpha`` is pinned before the run
(the catch-retention budget), so the gate cannot be over-fit to lower FAR.

Honest limitation (measured, not hidden): on the degenerate zero-event fixtures a
*reviewer-only defect* variant and its matched *clean* variant share identical data
and elicit identical "not estimable / CI includes 1" reasoning — so a flag on the
defect variant is a "right answer for a borderline reason" that is **inference-time
indistinguishable** from the clean-variant false alarm. Abstaining the false alarms
therefore also abstains a few such coincidental catches; that trade is exactly what
``alpha`` bounds and what the scorecard reports. There is no free lunch here — the
gap analysis's "FAR down, catch perfectly unchanged" was optimistic; the real
frontier costs a small, bounded catch retention which ``alpha`` makes explicit.

Zero third-party dependencies; pure functions so it is trivially testable and
cannot regress the hot path.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# --- Reason feature detectors (pinned before the run) ---------------------------
# SIG: the flag's basis is a statistical-significance / degenerate-data objection.
_SIG = re.compile(
    r"(includes?\s+1(\.0+)?\b|crosses?\s+1(\.0+)?\b|contains?\s+1(\.0+)?\b|"
    r"spans?\s+1(\.0+)?\b|includes?\s+(unity|the\s+null)|"
    r"non[-\s]?significan|not\s+significan|not\s+statistically|no\s+statistically\s+significan|"
    r"not\s+estimable|inestimable|undefined|uninformative|not\s+be\s+estimated|"
    r"cannot\s+be\s+(derived|estimated|computed)|no\s+effect\s+is\s+estimable|"
    r"zero[-\s]?events?|0\s+events|double[-\s]?zero|no\s+events|zero[-\s]information|"
    r"no[-\s]information|degenerate)",
    re.I,
)
# STRUCT: the flag cites a concrete structural / arithmetic defect (a real catch).
_STRUCT = re.compile(
    r"(mislabel|wrong\s+measure|measure\s+label|continuous|mean\s+difference|\bMD\b|\bSMD\b|"
    r"standardi[sz]ed\s+mean|"
    r"swap|swapped|comparator|reversed|arms?\s+(are\s+)?(swap|revers)|"
    r"missing\s+(a\s+)?(null|reference|control)|no\s+(null|reference)\s+arm|"
    r"absent\s+(null|reference)|historical\s+borrow|"
    r"naive\s+pool|copas|funnel|fixed[-\s]effect|random[-\s]effect|heterogeneity\s+method|"
    r"subgroup|analysis\s+label|impossible|events?\s+exceed|events?\s*>\s*n|transpos|"
    r"lo\s*>\s*hi|does\s+not\s+match|doesn'?t\s+match|reproduc)",
    re.I,
)

# Pinned confidence weights (declared before the run; never tuned on clean labels).
_BASE = 0.6
_STRUCT_BONUS = 0.4          # a concrete structural defect -> high confidence
_SIG_ONLY_PENALTY = 0.35     # flag rests ONLY on significance/degeneracy -> low
_CORROBORATION = 0.12        # per extra distinct flagging vendor
_DISSENT_PENALTY = 0.10      # a usable reviewer accepted (split panel), non-structural flag


def reason_is_sig_only(reason: str) -> bool:
    """A flag reason that raises a significance/degeneracy objection and cites NO
    concrete structural defect."""
    return bool(_SIG.search(reason or "")) and not bool(_STRUCT.search(reason or ""))


def reason_is_structural(reason: str) -> bool:
    return bool(_STRUCT.search(reason or ""))


@dataclass(slots=True)
class PanelSignals:
    n_flag_vendors: int          # distinct usable vendors that flagged
    n_usable_accepters: int      # usable reviewers that did NOT flag
    any_structural: bool         # >=1 usable flagger cited a structural defect
    all_sig_only: bool           # every usable flagger is significance/degeneracy-only


def panel_signals(reviewer_verdicts: list) -> PanelSignals:
    """Extract the pinned features from a panel of reviewer verdicts. A reviewer
    verdict is any object with ``.flag``, ``.reason``, ``.vendor``, ``.usable``."""
    usable = [v for v in reviewer_verdicts if getattr(v, "usable", True)]
    flaggers = [v for v in usable if getattr(v, "flag", False)]
    accepters = [v for v in usable if not getattr(v, "flag", False)]
    vendors = {getattr(v, "vendor", "") for v in flaggers}
    any_struct = any(reason_is_structural(getattr(v, "reason", "")) for v in flaggers)
    all_sig = bool(flaggers) and all(
        reason_is_sig_only(getattr(v, "reason", "")) for v in flaggers
    )
    return PanelSignals(len(vendors), len(accepters), any_struct, all_sig)


def flag_confidence(reviewer_verdicts: list) -> float:
    """Confidence in [0, 1] that a panel's flag is a real defect vs a borderline
    over-read. Returns 1.0 when no usable reviewer flagged (the gate only ever
    acts on a reviewer-driven flag; a non-flag is never abstained here)."""
    sig = panel_signals(reviewer_verdicts)
    if sig.n_flag_vendors == 0:
        return 1.0
    conf = _BASE
    if sig.any_structural:
        conf += _STRUCT_BONUS
    elif sig.all_sig_only:
        conf -= _SIG_ONLY_PENALTY
    conf += _CORROBORATION * (sig.n_flag_vendors - 1)
    if sig.n_usable_accepters >= 1 and not sig.any_structural:
        conf -= _DISSENT_PENALTY
    return max(0.0, min(1.0, round(conf, 4)))


# Sentinel returned when the gate must abstain NOTHING. Below every real confidence
# (which are in [0, 1]) so ``confidence <= NO_ABSTAIN`` is never true.
NO_ABSTAIN = -1.0


def calibrate_threshold(defect_confidences: list[float], *, alpha: float = 0.05) -> float:
    """Split-conformal threshold: the largest ``tau`` such that abstaining every
    flag with ``confidence <= tau`` costs at most a fraction ``alpha`` of the
    TRUE-DEFECT flags (catch-retention >= 1 - alpha). Calibrated on the defect class
    ONLY — clean-task outcomes are never used to pick ``tau``.

    Because the confidence score is DISCRETE (a handful of feature levels), the
    low-confidence flags cluster into ties. A naive ``alpha``-quantile with a strict
    ``<`` lands ON such a band and abstains none of it (over-retains, neutering the
    gate). Instead we take the largest confidence *value* whose full tie-group fits
    within the budget ``floor(alpha * n)`` and abstain ``confidence <= tau`` — so a
    tied borderline band is abstained as a whole, or not at all, never breaching the
    retention budget. With no defect flags or a zero budget, returns ``NO_ABSTAIN``
    (fail-open: we cannot bound catch loss, so the gate does nothing)."""
    import math
    xs = sorted(float(x) for x in defect_confidences)
    if not xs or alpha <= 0.0:
        return NO_ABSTAIN
    budget = int(math.floor(alpha * len(xs)))
    if budget <= 0:
        return NO_ABSTAIN
    tau = NO_ABSTAIN
    for v in sorted(set(xs)):
        if sum(1 for x in xs if x <= v) <= budget:
            tau = v            # this whole tie-group fits within the budget
        else:
            break              # values are ascending; no larger v can fit
    return tau


@dataclass(slots=True)
class ConformalGate:
    """A calibrated accept/abstain gate. ``tau`` is set by ``calibrate_threshold``
    (or pinned). ``decide`` maps a reviewer-driven flag to keep/abstain."""

    tau: float = NO_ABSTAIN      # default: abstain nothing (fail-open)
    alpha: float = 0.05          # recorded for provenance

    def should_abstain(self, reviewer_verdicts: list) -> bool:
        """True iff the panel's flag confidence is at or below the calibrated
        threshold (``<=`` so a tied borderline band abstains as a whole). Only
        meaningful when the panel actually produced a reviewer-driven flag; a
        ``tau`` of ``NO_ABSTAIN`` (-1.0) never fires (fail-open)."""
        return flag_confidence(reviewer_verdicts) <= self.tau

    def to_dict(self) -> dict:
        return {"tau": round(self.tau, 4), "alpha": self.alpha}


def gate_from_defect_flags(reviewer_records_by_task: dict, defect_ids: set,
                           *, alpha: float = 0.05) -> ConformalGate:
    """Build a calibrated gate from a run's reviewer records.

    ``reviewer_records_by_task`` maps task_id -> list of reviewer verdicts (objects
    or dicts with flag/reason/vendor/usable). ``defect_ids`` is the set of task ids
    that are TRUE defects (the scorer supplies this — the only key access). The gate
    is calibrated to retain ``>= (1 - alpha)`` of the reviewer-driven defect flags."""
    confs = []
    for tid in defect_ids:
        revs = reviewer_records_by_task.get(tid)
        if not revs:
            continue
        revs = [_as_verdict(r) for r in revs]
        # only defect tasks with a reviewer-driven flag inform the threshold
        if any(getattr(v, "flag", False) and getattr(v, "usable", True) for v in revs):
            confs.append(flag_confidence(revs))
    tau = calibrate_threshold(confs, alpha=alpha)
    return ConformalGate(tau=tau, alpha=alpha)


@dataclass(slots=True)
class _RV:
    flag: bool
    reason: str = ""
    vendor: str = ""
    usable: bool = True


def _as_verdict(r):
    """Accept either a ReviewerVerdict-like object or a plain dict record."""
    if isinstance(r, dict):
        return _RV(flag=bool(r.get("flag")), reason=r.get("reason", "") or "",
                   vendor=r.get("vendor", "") or "", usable=bool(r.get("usable", True)))
    return r
