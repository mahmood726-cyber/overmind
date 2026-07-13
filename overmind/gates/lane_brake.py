"""Gate 5 — the elaboration brake. F5's fix.

F5: ~30 lanes in two days, several pure ornament; Mahmood had to invoke the
Fatiha to pull the harness back. There was no cost to starting a lane and no
periodic test of "does this serve the researcher in Kampala?".

The fix: a lane costs something to start. Every lane must answer, concretely,
which failure or which Kampala datum it serves, and name a deliverable, an
evidence source, and a STOP condition. A lane that cannot answer is refused —
before it consumes a single token. There is also a hard cap on concurrent lanes
so the harness cannot fan out into ornament.

"Serves Kampala" is the ranking axis for the whole package: a lane must make the
open-access, more-truthful-than-the-well-resourced answer better, or it does not
start.
"""
from __future__ import annotations

from dataclasses import dataclass, field

MAX_CONCURRENT_LANES = 3   # throttle: matches the "max 2-3 concurrent agents" rule

# A lane must serve at least one of these. Free text that maps to neither is
# treated as ornament and refused.
_KNOWN_FAILURES = {"F1", "F2", "F3", "F4", "F5", "F6", "F7"}


@dataclass(slots=True)
class LaneSpec:
    name: str
    serves: str            # a failure id (F1..F7) OR a concrete Kampala datum
    beneficiary: str       # who is better off — must be concrete, not "the field"
    deliverable: str       # the artifact this lane produces
    evidence_source: str   # the data it stands on (path / registry / corpus)
    stop_condition: str    # what "done" is — no open-ended lanes
    kampala_datum: str = ""  # the specific open-access fact it improves, if any


class LaneRefused(RuntimeError):
    """Raised when a lane does not justify its own existence."""


_VAGUE = {"", "n/a", "na", "tbd", "the field", "science", "general",
          "improve things", "explore", "misc", "various"}


def _blank(s: str) -> bool:
    return (s or "").strip().lower() in _VAGUE


def admit_lane(spec: LaneSpec, *, active: int = 0) -> LaneSpec:
    """Fail closed unless the lane justifies itself and there is budget for it."""
    if active >= MAX_CONCURRENT_LANES:
        raise LaneRefused(
            f"BLOCKED: {spec.name!r} — already {active} concurrent lanes "
            f"(cap {MAX_CONCURRENT_LANES}). Finish or drop one before starting "
            f"another. Uncontrolled fan-out is F5."
        )
    serves_failure = spec.serves.strip().upper() in _KNOWN_FAILURES
    serves_kampala = not _blank(spec.kampala_datum)
    if not (serves_failure or serves_kampala):
        raise LaneRefused(
            f"BLOCKED: {spec.name!r} serves neither a named failure (F1-F7) nor "
            f"a concrete Kampala datum (serves={spec.serves!r}, "
            f"kampala_datum={spec.kampala_datum!r}). This is how ornament starts "
            f"— name who in Kampala is better off, or do not start."
        )
    for label, val in (("beneficiary", spec.beneficiary),
                       ("deliverable", spec.deliverable),
                       ("evidence_source", spec.evidence_source),
                       ("stop_condition", spec.stop_condition)):
        if _blank(val):
            raise LaneRefused(
                f"BLOCKED: {spec.name!r} has no concrete {label} "
                f"(got {val!r}). Every lane needs a real {label} before it starts."
            )
    return spec
