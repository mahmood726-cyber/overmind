"""Gate 3 — the blind-spot map. F3's fix.

F3: three defences (arithmetic, transparency, the 3-model panel) were all blind
in the SAME place — every one checks whether THE NUMBER is right; none checks
WHAT IT IS A NUMBER OF. Their agreement felt like safety. Agreement between
defences that share a blind spot is the blind spot, tripled.

The fix: every check DECLARES the error classes it cannot see. This module
computes coverage-by-error-class over the checks actually applied to a claim,
and makes a SHARED blind spot a LOUD failure (BlindSpotError) instead of a quiet
consensus. If every applied check is blind to SELECTION, the pipeline stops and
says so — it does not let three green checkmarks stand in for looking.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ErrorClass(str, Enum):
    """The ways a reported number can be wrong. Distinct axes, not severities."""
    TRANSCRIPTION = "transcription"        # right cell, wrong digits copied
    SELECTION = "selection"                # wrong number entirely: what is it OF?
    REACH_VS_ACCURACY = "reach_vs_accuracy"  # missing data scored as a wrong answer
    FABRICATION = "fabrication"            # number has no source at all
    SYCOPHANCY = "sycophancy"              # number bent toward a desired conclusion
    PRIOR_ART = "prior_art"                # novelty claim that is not novel


ALL_ERROR_CLASSES = tuple(ErrorClass)


@dataclass(frozen=True, slots=True)
class Check:
    """A defence, with an honest declaration of what it CANNOT see.

    ``sees`` and ``blind_to`` must partition ALL_ERROR_CLASSES — a check that
    does not name where it is blind is not admitted (you cannot hide a blind
    spot by omission).

    ``proven`` is the subset of ``sees`` that is backed by a capability trip
    fixture in the test suite (``test_gate3_declared_sight_is_proven``). Both
    external reviewers (2026-07-13) warned that a declaration is worthless if a
    check can just claim ``sees=ALL``. So the strong coverage check counts only
    ``proven``, not ``sees`` — a class you claim to catch but cannot demonstrate
    catching does not close the blind spot.
    """
    name: str
    sees: frozenset[ErrorClass]
    blind_to: frozenset[ErrorClass]
    proven: frozenset[ErrorClass] = frozenset()

    def __post_init__(self):
        covered = self.sees | self.blind_to
        if covered != frozenset(ALL_ERROR_CLASSES):
            missing = frozenset(ALL_ERROR_CLASSES) - covered
            raise ValueError(
                f"check {self.name!r} must declare every error class as seen or "
                f"blind; undeclared: {sorted(m.value for m in missing)}"
            )
        if self.sees & self.blind_to:
            raise ValueError(f"check {self.name!r}: a class is both seen and blind")
        if not (self.proven <= self.sees):
            raise ValueError(
                f"check {self.name!r}: cannot 'prove' a class it does not claim "
                f"to see: {sorted((self.proven - self.sees))}")


# The three defences that shared a blind spot on 2026-07-13, declared honestly.
DEFAULT_CHECKS: dict[str, Check] = {
    "arithmetic": Check(
        "arithmetic",
        sees=frozenset({ErrorClass.TRANSCRIPTION}),
        blind_to=frozenset({ErrorClass.SELECTION, ErrorClass.REACH_VS_ACCURACY,
                            ErrorClass.FABRICATION, ErrorClass.SYCOPHANCY,
                            ErrorClass.PRIOR_ART}),
    ),
    "transparency": Check(
        "transparency",
        sees=frozenset({ErrorClass.TRANSCRIPTION}),
        blind_to=frozenset({ErrorClass.SELECTION, ErrorClass.REACH_VS_ACCURACY,
                            ErrorClass.FABRICATION, ErrorClass.SYCOPHANCY,
                            ErrorClass.PRIOR_ART}),
    ),
    "same_family_panel": Check(
        "same_family_panel",
        sees=frozenset({ErrorClass.TRANSCRIPTION}),
        blind_to=frozenset({ErrorClass.SELECTION, ErrorClass.REACH_VS_ACCURACY,
                            ErrorClass.FABRICATION, ErrorClass.SYCOPHANCY,
                            ErrorClass.PRIOR_ART}),
    ),
    # The gates in THIS package are the checks that close those blind spots:
    "export_gate": Check(
        "export_gate",
        sees=frozenset({ErrorClass.FABRICATION}),
        blind_to=frozenset({ErrorClass.TRANSCRIPTION, ErrorClass.SELECTION,
                            ErrorClass.REACH_VS_ACCURACY, ErrorClass.SYCOPHANCY,
                            ErrorClass.PRIOR_ART}),
        proven=frozenset({ErrorClass.FABRICATION}),   # test_gate1_* trips it
    ),
    "layer_gate": Check(
        "layer_gate",
        sees=frozenset({ErrorClass.SELECTION, ErrorClass.REACH_VS_ACCURACY}),
        blind_to=frozenset({ErrorClass.TRANSCRIPTION, ErrorClass.FABRICATION,
                            ErrorClass.SYCOPHANCY, ErrorClass.PRIOR_ART}),
        proven=frozenset({ErrorClass.SELECTION, ErrorClass.REACH_VS_ACCURACY}),
    ),
    "cross_family_panel": Check(
        "cross_family_panel",
        sees=frozenset({ErrorClass.SYCOPHANCY, ErrorClass.PRIOR_ART}),
        blind_to=frozenset({ErrorClass.TRANSCRIPTION, ErrorClass.SELECTION,
                            ErrorClass.REACH_VS_ACCURACY, ErrorClass.FABRICATION}),
        proven=frozenset({ErrorClass.SYCOPHANCY, ErrorClass.PRIOR_ART}),
    ),
}


class BlindSpotError(RuntimeError):
    """Raised when, across the applied checks, an error class is seen by NONE."""


def coverage_report(checks, *, proven_only: bool = False) -> dict[ErrorClass, list[str]]:
    """Map each error class -> the applied checks that can see it. An empty list
    is a shared blind spot. With ``proven_only``, only classes a check has a
    capability fixture for are counted (a mere ``sees=`` declaration does not)."""
    report: dict[ErrorClass, list[str]] = {ec: [] for ec in ALL_ERROR_CLASSES}
    for chk in checks:
        seen = chk.proven if proven_only else chk.sees
        for ec in seen:
            report[ec].append(chk.name)
    return report


def assert_no_shared_blindspot(checks, *, require=ALL_ERROR_CLASSES,
                               proven_only: bool = False) -> dict:
    """LOUD failure if any required error class is covered by zero applied checks.

    This is the anti-F3 core: three checks that all say "number OK" while all
    being blind to SELECTION is not consensus, it is a hole. Passing three checks
    that share a blind spot must fail here, not read as agreement.

    ``proven_only=True`` is the strong form: a class only counts as covered if a
    check has demonstrated (via a trip fixture) that it actually catches it —
    closing the "a check just declares sees=ALL" bypass both reviewers named.
    """
    report = coverage_report(checks, proven_only=proven_only)
    holes = [ec for ec in require if not report[ec]]
    if holes:
        raise BlindSpotError(
            "SHARED BLIND SPOT — no applied check can see: "
            + ", ".join(sorted(h.value for h in holes))
            + f". Applied checks: {[c.name for c in checks]}. "
            "Agreement among these is the blind spot, not safety. Add a check "
            "that sees the missing class (e.g. layer_gate for selection, "
            "cross_family_panel for sycophancy/prior-art) before reporting."
        )
    return report
