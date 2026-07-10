"""Fail-closed consensus-or-flag resolution (hardening/consensus-verifier-2026-07-10).

The north-star primitive of this harness is *heterogeneous-vendor reproduction
with truth-gating*: N different-family vendors reproduce a result, and the harness
only ships when they genuinely corroborate — otherwise it FLAGS. This module is
the single **deterministic, fail-closed** resolver for that decision.

Why a new module (see the branch weakness assessment W1–W5):
  * ``QuorumJudge`` (llm_judge.py) resolves a verdict by nominal pass-ratio and
    returns ``passed=True`` when too few backends respond or a backend raises,
    deferring the fail-closed safety to the *orchestrator reading a
    ``judge_error`` concern string*. A success predicate that lives in a different
    module reading a flag is the verification-theater family — one caller that
    checks ``.passed`` alone silently ships an all-vendors-down verdict.
  * ``decorrelation_gate`` (judge_factory.py) — the rule that *correlated
    agreement is not consensus* — is defined but only ever called from the
    observational provenance path, never in the decision path.
  * There is no primitive that separates a numeric **near-miss** (within
    tolerance — still agreement) from a **real disagreement** (outside tolerance).

This module makes the fail-closed decision explicit, in one pure place:

  * **Pure** — no LLM calls, no network, no filesystem, no clock. Trivially
    testable, offline-serializable, cannot regress the hot path.
  * **Fail-closed** — every ambiguous input resolves to ``FLAGGED``, never
    ``CONSENSUS_PASS``: too few usable vendors, timeout/error/malformed responses
    dropping usable witnesses below the floor, a correlated panel below the
    effective-vote floor, numeric disagreement outside tolerance, or a required
    objective witness that is absent.
  * **Witness-binding** — the outcome records exactly which vendors witnessed it,
    their families, the effective independent-vote count, and whether an objective
    witness sat under the pass.

It reuses ``judge_factory``'s family map + Kish n_eff so the independence math is
not duplicated (that import performs no I/O at load time).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from overmind.verification.judge_factory import family_for_engine, kish_neff

# --- Tolerance discipline (Target #2) -------------------------------------------
# Numeric agreement tolerance is EXPLICIT and documented. Two vendor numbers agree
# iff their spread is within ``atol + rtol * scale`` where ``scale`` is the largest
# magnitude among the compared values (a relative band with an absolute floor for
# values near zero). These defaults match the repo's R/metafor parity tolerance
# (1e-6, see rules/advanced-stats.md "R validation") so numeric consensus uses the
# same yardstick as the numerical-continuity witness rather than a second, looser
# one. A value strictly within the band but not bit-identical is a *near-miss*
# (still agreement); anything outside the band is a real disagreement.
DEFAULT_RTOL: float = 1e-6
DEFAULT_ATOL: float = 1e-9

# --- Witness floor discipline (Target #3) ---------------------------------------
# Consensus requires enough *independent* witnesses. Defaults align with
# judge_factory's decorrelation gate (>=2 distinct model families, n_eff >= 2).
DEFAULT_MIN_USABLE_WITNESSES: int = 2
DEFAULT_MIN_INDEPENDENT_FAMILIES: int = 2
DEFAULT_MIN_EFFECTIVE_VOTES: float = 2.0


class VendorStatus(str, Enum):
    """Delivery status of one vendor's contribution to a consensus.

    Only ``OK`` responses are counted as votes. Every other status is an
    **abstention**: it is excluded from the agreement numerator/denominator, but
    it still counts against the "did enough independent witnesses actually
    respond" floor — so a panel that mostly timed out fails closed instead of
    letting the one survivor's PASS masquerade as consensus.
    """

    OK = "ok"                    # usable, parseable verdict/value
    TIMEOUT = "timeout"          # vendor did not answer in time
    ERROR = "error"             # backend error / auth failure / judge_error
    MALFORMED = "malformed"      # answered, but unparseable / degenerate
    UNAVAILABLE = "unavailable"  # backend not live / not configured


# Statuses that represent a vendor that did not deliver a usable vote.
ABSTENTION_STATUSES: frozenset[VendorStatus] = frozenset(
    {VendorStatus.TIMEOUT, VendorStatus.ERROR, VendorStatus.MALFORMED, VendorStatus.UNAVAILABLE}
)


class ConsensusVerdict(str, Enum):
    """The three — and only three — outcomes. There is no silent pass."""

    CONSENSUS_PASS = "consensus_pass"   # enough independent witnesses corroborate PASS
    CONSENSUS_FAIL = "consensus_fail"   # enough independent witnesses corroborate FAIL
    FLAGGED = "flagged"                 # ambiguous — must go to human / objective witness


class FlagReason(str, Enum):
    """Why a resolution was flagged. Ordered roughly by precedence of reporting."""

    NO_USABLE_RESPONSES = "no_usable_responses"
    INSUFFICIENT_WITNESSES = "insufficient_witnesses"
    CORRELATED_PANEL = "correlated_panel"
    DISAGREEMENT = "disagreement"
    NUMERIC_DISAGREEMENT = "numeric_disagreement"
    MISSING_OBJECTIVE_WITNESS = "missing_objective_witness"


@dataclass(slots=True)
class VendorResponse:
    """One vendor's contribution to a consensus decision.

    ``vendor`` is an engine name (e.g. ``"claude"``, ``"codex"``); the model family
    is derived from it unless ``family`` is given explicitly. ``passed`` is the
    vendor's boolean verdict (``None`` for a pure numeric witness). ``value`` is an
    optional numeric answer for numeric-agreement checks.
    """

    vendor: str
    status: VendorStatus = VendorStatus.OK
    passed: bool | None = None
    value: float | None = None
    family: str | None = None
    detail: str = ""

    @property
    def resolved_family(self) -> str:
        return self.family if self.family else family_for_engine(self.vendor)

    @property
    def is_usable(self) -> bool:
        """A usable vote: delivered OK *and* carries a boolean verdict."""
        return self.status == VendorStatus.OK and self.passed is not None

    def to_dict(self) -> dict:
        return {
            "vendor": self.vendor,
            "family": self.resolved_family,
            "status": self.status.value,
            "passed": self.passed,
            "value": self.value,
            "detail": self.detail,
        }


class NumericAgreement(str, Enum):
    AGREE = "agree"        # all values within tolerance (identical or near-miss)
    DISAGREE = "disagree"  # at least one value outside tolerance
    UNKNOWN = "unknown"    # fewer than two numeric values to compare


@dataclass(slots=True)
class NumericConsensus:
    """Outcome of a numeric agreement check across vendor values."""

    agreement: NumericAgreement
    n_values: int
    spread: float             # max - min across the compared values
    tolerance: float          # the band actually used (atol + rtol * scale)
    near_miss: bool           # within tolerance but not bit-identical
    rtol: float
    atol: float

    def to_dict(self) -> dict:
        return {
            "agreement": self.agreement.value,
            "n_values": self.n_values,
            "spread": self.spread,
            "tolerance": self.tolerance,
            "near_miss": self.near_miss,
            "rtol": self.rtol,
            "atol": self.atol,
        }


def numeric_consensus(
    values: list[float],
    *,
    rtol: float = DEFAULT_RTOL,
    atol: float = DEFAULT_ATOL,
) -> NumericConsensus:
    """Classify whether numeric vendor answers agree within an explicit tolerance.

    Two or more values AGREE iff their spread ``max - min`` is ``<= atol + rtol *
    scale`` where ``scale = max(|v|)``. A spread strictly greater than zero but
    within the band is a **near-miss** (floating-point / implementation jitter —
    still agreement). Anything outside the band is a real DISAGREEMENT and must be
    flagged by the caller.

    Non-finite values (NaN / inf) are treated as a disagreement (fail-closed): a
    vendor that produced NaN has not corroborated anything.
    """
    present = [v for v in values if v is not None]
    finite = [v for v in present if isinstance(v, (int, float)) and math.isfinite(v)]
    had_nonfinite = len(finite) != len(present)
    if len(present) < 2:
        # Nothing to compare (0/1 values) — UNKNOWN; the witness floor in
        # resolve_consensus handles insufficiency.
        return NumericConsensus(
            agreement=NumericAgreement.UNKNOWN,
            n_values=len(finite),
            spread=0.0,
            tolerance=atol,
            near_miss=False,
            rtol=rtol,
            atol=atol,
        )
    if had_nonfinite:
        # A NaN/inf answer alongside another value — never call that agreement.
        # (>=2 values present, so there IS something it fails to corroborate.)
        lo = min(finite) if finite else 0.0
        hi = max(finite) if finite else 0.0
        return NumericConsensus(
            agreement=NumericAgreement.DISAGREE, n_values=len(finite), spread=hi - lo,
            tolerance=atol + rtol * max(abs(lo), abs(hi)), near_miss=False, rtol=rtol, atol=atol,
        )
    lo, hi = min(finite), max(finite)
    spread = hi - lo
    scale = max(abs(lo), abs(hi))
    tol = atol + rtol * scale
    within = spread <= tol
    return NumericConsensus(
        agreement=NumericAgreement.AGREE if within else NumericAgreement.DISAGREE,
        n_values=len(finite),
        spread=spread,
        tolerance=tol,
        near_miss=bool(within and spread > 0.0),
        rtol=rtol,
        atol=atol,
    )


@dataclass(slots=True)
class ConsensusOutcome:
    """Result of ``resolve_consensus`` — fail-closed, witness-bound.

    ``verdict`` is the single source of truth. ``passed`` is a convenience alias
    that is True **only** for ``CONSENSUS_PASS`` — a FLAGGED or CONSENSUS_FAIL
    outcome is never truthy, so a caller cannot accidentally ship on a flag.
    """

    verdict: ConsensusVerdict
    reasons: list[FlagReason] = field(default_factory=list)
    # witness binding (Target #3)
    witnesses: list[str] = field(default_factory=list)        # usable voters (engine names)
    witness_families: list[str] = field(default_factory=list)  # distinct families among witnesses
    abstentions: list[dict] = field(default_factory=list)      # non-OK vendors + why
    n_usable: int = 0
    n_pass: int = 0
    n_fail: int = 0
    distinct_families: int = 0
    effective_votes: float = 0.0
    objective_witness_present: bool = False
    numeric: NumericConsensus | None = None
    note: str = ""

    @property
    def passed(self) -> bool:
        return self.verdict == ConsensusVerdict.CONSENSUS_PASS

    @property
    def flagged(self) -> bool:
        return self.verdict == ConsensusVerdict.FLAGGED

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "passed": self.passed,
            "flagged": self.flagged,
            "reasons": [r.value for r in self.reasons],
            "witnesses": list(self.witnesses),
            "witness_families": list(self.witness_families),
            "abstentions": list(self.abstentions),
            "n_usable": self.n_usable,
            "n_pass": self.n_pass,
            "n_fail": self.n_fail,
            "distinct_families": self.distinct_families,
            "effective_votes": self.effective_votes,
            "objective_witness_present": self.objective_witness_present,
            "numeric": self.numeric.to_dict() if self.numeric else None,
            "note": self.note,
        }


def resolve_consensus(
    responses: list[VendorResponse],
    *,
    min_usable_witnesses: int = DEFAULT_MIN_USABLE_WITNESSES,
    min_independent_families: int = DEFAULT_MIN_INDEPENDENT_FAMILIES,
    min_effective_votes: float = DEFAULT_MIN_EFFECTIVE_VOTES,
    require_objective_witness: bool = False,
    objective_witness_present: bool = False,
    rtol: float = DEFAULT_RTOL,
    atol: float = DEFAULT_ATOL,
) -> ConsensusOutcome:
    """Resolve a set of vendor responses to CONSENSUS_PASS / CONSENSUS_FAIL /
    FLAGGED — fail-closed.

    Consensus (either direction) requires that the usable, independent witnesses
    are unanimous. Anything ambiguous flags:

      * no usable responses ......................... FLAGGED (NO_USABLE_RESPONSES)
      * usable < ``min_usable_witnesses`` ........... FLAGGED (INSUFFICIENT_WITNESSES)
      * distinct families < ``min_independent_families``
        or n_eff < ``min_effective_votes`` .......... FLAGGED (CORRELATED_PANEL)
      * some usable PASS and some FAIL .............. FLAGGED (DISAGREEMENT)
      * numeric values outside tolerance ............ FLAGGED (NUMERIC_DISAGREEMENT)
      * ``require_objective_witness`` and none present  FLAGGED (MISSING_OBJECTIVE_WITNESS)

    Only when every floor is met, the independent witnesses are unanimous, any
    numeric answers agree within tolerance, and (if required) an objective witness
    is present, does this return CONSENSUS_PASS (all passed) or CONSENSUS_FAIL (all
    failed — a decisive, corroborated negative, not a flag).

    A unanimous FAIL is CONSENSUS_FAIL even when an objective witness is absent:
    corroborating a failure never needs an extra witness to be safe. The objective-
    witness requirement only guards the *pass* direction (the dangerous one).
    """
    usable = [r for r in responses if r.is_usable]
    abstentions = [r.to_dict() for r in responses if not r.is_usable]

    witnesses = [r.vendor for r in usable]
    families_in_order: list[str] = []
    for r in usable:
        fam = r.resolved_family
        if fam not in families_in_order:
            families_in_order.append(fam)
    distinct = len(families_in_order)
    neff = kish_neff(witnesses) if witnesses else 0.0

    n_pass = sum(1 for r in usable if r.passed)
    n_fail = len(usable) - n_pass

    # numeric agreement across usable vendors that carry a value
    numeric_vals = [r.value for r in usable if r.value is not None]
    numeric = numeric_consensus(numeric_vals, rtol=rtol, atol=atol) if numeric_vals else None

    reasons: list[FlagReason] = []

    # --- Floor checks (order matters only for reporting) ---
    if not usable:
        return ConsensusOutcome(
            verdict=ConsensusVerdict.FLAGGED,
            reasons=[FlagReason.NO_USABLE_RESPONSES],
            witnesses=[], witness_families=[], abstentions=abstentions,
            n_usable=0, n_pass=0, n_fail=0, distinct_families=0, effective_votes=0.0,
            objective_witness_present=objective_witness_present, numeric=numeric,
            note="no vendor delivered a usable verdict — cannot corroborate anything",
        )

    disagreement = n_pass > 0 and n_fail > 0
    numeric_disagreement = numeric is not None and numeric.agreement == NumericAgreement.DISAGREE

    # Witness-count / independence floors apply to *corroboration*. A genuine,
    # unanimous split-free FAIL is still allowed to resolve as CONSENSUS_FAIL below
    # even if it comes from a single family, because a corroborated failure is the
    # safe direction; the floors gate the PASS direction. But an explicit
    # DISAGREEMENT always flags regardless of counts.
    if disagreement:
        reasons.append(FlagReason.DISAGREEMENT)
    if numeric_disagreement:
        reasons.append(FlagReason.NUMERIC_DISAGREEMENT)

    if disagreement or numeric_disagreement:
        return ConsensusOutcome(
            verdict=ConsensusVerdict.FLAGGED,
            reasons=reasons,
            witnesses=witnesses, witness_families=families_in_order, abstentions=abstentions,
            n_usable=len(usable), n_pass=n_pass, n_fail=n_fail,
            distinct_families=distinct, effective_votes=neff,
            objective_witness_present=objective_witness_present, numeric=numeric,
            note="vendors disagree — flagged for adjudication, never silently resolved",
        )

    # Unanimous now (no split). Decide direction.
    unanimous_pass = n_pass == len(usable)

    if not unanimous_pass:
        # Unanimous FAIL — decisive corroborated negative. Safe direction.
        return ConsensusOutcome(
            verdict=ConsensusVerdict.CONSENSUS_FAIL,
            reasons=[],
            witnesses=witnesses, witness_families=families_in_order, abstentions=abstentions,
            n_usable=len(usable), n_pass=n_pass, n_fail=n_fail,
            distinct_families=distinct, effective_votes=neff,
            objective_witness_present=objective_witness_present, numeric=numeric,
            note=f"{n_fail}/{len(usable)} usable witnesses corroborate FAIL",
        )

    # Unanimous PASS — the dangerous direction. Enforce every floor fail-closed.
    if len(usable) < min_usable_witnesses:
        reasons.append(FlagReason.INSUFFICIENT_WITNESSES)
    if distinct < min_independent_families or neff < min_effective_votes:
        reasons.append(FlagReason.CORRELATED_PANEL)
    if require_objective_witness and not objective_witness_present:
        reasons.append(FlagReason.MISSING_OBJECTIVE_WITNESS)

    if reasons:
        return ConsensusOutcome(
            verdict=ConsensusVerdict.FLAGGED,
            reasons=reasons,
            witnesses=witnesses, witness_families=families_in_order, abstentions=abstentions,
            n_usable=len(usable), n_pass=n_pass, n_fail=n_fail,
            distinct_families=distinct, effective_votes=neff,
            objective_witness_present=objective_witness_present, numeric=numeric,
            note="unanimous PASS but a corroboration floor was not met — flagged, not shipped",
        )

    return ConsensusOutcome(
        verdict=ConsensusVerdict.CONSENSUS_PASS,
        reasons=[],
        witnesses=witnesses, witness_families=families_in_order, abstentions=abstentions,
        n_usable=len(usable), n_pass=n_pass, n_fail=n_fail,
        distinct_families=distinct, effective_votes=neff,
        objective_witness_present=objective_witness_present, numeric=numeric,
        note=(
            f"{n_pass}/{len(usable)} independent witnesses ({distinct} families, "
            f"n_eff={neff}) corroborate PASS"
        ),
    )
