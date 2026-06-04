"""Reporting-bias / missing-evidence accounting — first-class, deterministic.

An honest synthesis must surface what is MISSING, not just pool what is present.
This module makes three missing-evidence signals first-class outputs:

  1. registry_linkage(): the registry-vs-publication denominator. Only ~63.6% of
     registered trials publish results (TrialScout, medRxiv 2026.03.15), so an MA
     that cites N trials sits on a denominator of ~N/0.636 registered trials. We
     compute the linkage rate and the implied missing-trial count rather than
     silently treating the published set as "all trials".
  2. missing_evidence_robme(): a TRANSPARENT, threshold-based ROB-ME scaffold
     (Cochrane Handbook Ch.13, 2024+). It is decision SUPPORT, not an automated
     verdict — it aggregates the linkage rate, unpublished count, and an optional
     small-study-effect signal into a flagged concern level with explicit reasons.
  3. outcome_switching_summary(): protocol-vs-paper outcome drift, with the ITS
     base-rate context (~24% of pre-specified outcomes silently dropped; medRxiv
     2025.11.06). Wraps prisma.outcome_switching so it is reported as a bias signal.

All deterministic, offline, stdlib-only. Validation fails closed.
"""
from __future__ import annotations

# Literature base rates (cited; used as CONTEXT, never as a substitute for the
# study's own numbers). Re-verify before external citation.
LINKAGE_BASE_RATE = 0.636          # TrialScout, medRxiv 2026.03.15
OUTCOME_SWITCH_BASE_RATE = 0.24    # ITS pre-specified-outcome drop rate, medRxiv 2025.11.06

# ROB-ME concern thresholds (transparent, documented — not a hidden model).
_LINKAGE_HIGH_CONCERN = 0.50       # < this share published -> high missing-evidence risk
_LINKAGE_SOME_CONCERN = 0.80       # < this -> some concerns


def registry_linkage(n_registered: int, n_published: int, n_in_review: int | None = None) -> dict:
    """Registry-vs-publication denominator. ``n_in_review`` = trials the synthesis
    actually included (optional), used to project the registered-trial denominator."""
    if n_registered <= 0:
        raise ValueError("n_registered must be > 0")
    if not (0 <= n_published <= n_registered):
        raise ValueError(f"n_published ({n_published}) must be in [0, n_registered={n_registered}]")
    linkage = n_published / n_registered
    unpublished = n_registered - n_published
    out = {
        "capability": "registry_publication_linkage",
        "n_registered": n_registered,
        "n_published": n_published,
        "n_unpublished": unpublished,
        "linkage_rate": round(linkage, 4),
        "unpublished_fraction": round(1 - linkage, 4),
        "base_rate_reference": LINKAGE_BASE_RATE,
        "below_base_rate": linkage < LINKAGE_BASE_RATE,
        "note": (
            "the published set is NOT the trial denominator; "
            f"{unpublished} registered trial(s) are unpublished (missing-evidence risk)"
        ),
    }
    if n_in_review is not None:
        if n_in_review < 0:
            raise ValueError("n_in_review must be >= 0")
        # If the review's included trials are drawn from the published set, the
        # registered-trial denominator they represent is n_in_review / linkage.
        projected = round(n_in_review / linkage, 1) if linkage > 0 else None
        out["n_in_review"] = n_in_review
        out["projected_registered_denominator"] = projected
        out["note"] += (
            f"; the {n_in_review} included trial(s) project to ~{projected} registered "
            "trials at the observed linkage rate"
        )
    return out


def missing_evidence_robme(
    linkage_rate: float,
    n_unpublished: int,
    small_study_effect: bool | None = None,
    funnel_asymmetry_p: float | None = None,
) -> dict:
    """Transparent ROB-ME scaffold: flag missing-evidence concern from inputs.
    Decision SUPPORT only — a human makes the ROB-ME judgement. Levels mirror RoB:
    'low' / 'some-concerns' / 'high'."""
    if not (0.0 <= linkage_rate <= 1.0):
        raise ValueError("linkage_rate must be in [0,1]")
    if n_unpublished < 0:
        raise ValueError("n_unpublished must be >= 0")
    reasons: list[str] = []
    level = "low"

    if linkage_rate < _LINKAGE_HIGH_CONCERN:
        level = "high"
        reasons.append(f"only {linkage_rate:.0%} of registered trials published (< {_LINKAGE_HIGH_CONCERN:.0%})")
    elif linkage_rate < _LINKAGE_SOME_CONCERN:
        level = "some-concerns"
        reasons.append(f"{linkage_rate:.0%} publication linkage (< {_LINKAGE_SOME_CONCERN:.0%})")

    asym = small_study_effect is True or (funnel_asymmetry_p is not None and funnel_asymmetry_p < 0.10)
    if asym:
        reasons.append("small-study-effect / funnel asymmetry signal present")
        level = "high" if level != "low" else "some-concerns"

    if n_unpublished > 0 and level == "low":
        level = "some-concerns"
        reasons.append(f"{n_unpublished} unpublished registered trial(s)")

    if not reasons:
        reasons.append("no missing-evidence signal exceeded a threshold")
    return {
        "capability": "rob_me_scaffold",
        "standard": "Cochrane Handbook Ch.13 (ROB-ME), 2024+",
        "concern_level": level,
        "reasons": reasons,
        "is_decision_support": True,
        "policy": "transparent threshold scaffold; a human makes the ROB-ME judgement, this does not auto-decide",
    }


def outcome_switching_summary(protocol_outcomes: list[str], reported_outcomes: list[str]) -> dict:
    """Protocol-vs-paper outcome drift as a reporting-bias signal, with base-rate context."""
    from overmind.evidence.prisma import outcome_switching
    r = outcome_switching(protocol_outcomes, reported_outcomes)
    r["base_rate_reference"] = OUTCOME_SWITCH_BASE_RATE
    r["base_rate_note"] = (
        f"~{OUTCOME_SWITCH_BASE_RATE:.0%} of pre-specified outcomes are silently dropped in ITS "
        "(medRxiv 2025.11.06); undisclosed drops are a high-RoB reporting-bias signal"
    )
    return r


def reporting_bias_report(
    n_registered: int,
    n_published: int,
    n_in_review: int | None = None,
    protocol_outcomes: list[str] | None = None,
    reported_outcomes: list[str] | None = None,
    small_study_effect: bool | None = None,
    funnel_asymmetry_p: float | None = None,
) -> dict:
    """Bundle the missing-evidence signals into one first-class artifact."""
    linkage = registry_linkage(n_registered, n_published, n_in_review)
    robme = missing_evidence_robme(
        linkage["linkage_rate"], linkage["n_unpublished"],
        small_study_effect=small_study_effect, funnel_asymmetry_p=funnel_asymmetry_p,
    )
    report = {
        "capability": "reporting_bias_accounting",
        "linkage": linkage,
        "rob_me": robme,
    }
    if protocol_outcomes is not None and reported_outcomes is not None:
        report["outcome_switching"] = outcome_switching_summary(protocol_outcomes, reported_outcomes)
    return report
