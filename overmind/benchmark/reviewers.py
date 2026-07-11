"""Reviewers: the per-arm model callables + a deterministic stub (§3).

A reviewer sees ONLY the task artifact and returns a ReviewerVerdict (flag +
reason + optional value). Real reviewers wrap a judge backend (Claude / Codex /
Gemini); the StubReviewer is scripted per task id for tests/dry-runs (no quota).

The reviewer prompt is built from the artifact ONLY — the answer key is never in
scope (blinding).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from overmind.benchmark.tasks import Task

REVIEW_INSTRUCTION = (
    "You are an independent reviewer of a meta-analysis artifact. Decide whether it "
    "contains a real defect: an arithmetically impossible 2x2 cell (events > N), a "
    "pooled estimate that does not match the data, or a stated conclusion whose "
    "direction contradicts the data. Answer on two lines exactly:\n"
    "FLAG: yes|no\n"
    "REASON: <one line>\n"
    "If you compute a corrected pooled estimate, add 'VALUE: <number>'."
)

# PV-A (precision fix #1 + #3): the calibrated reviewer instruction. Two changes vs
# REVIEW_INSTRUCTION, both principled (tuned to the DEFECT DEFINITION, never to the
# clean labels):
#   (1) a non-significant result is NOT a defect. A 95% CI that crosses 1.0 (or a
#       wide/non-significant interval) is a statement about PRECISION, not direction.
#       A direction defect requires the pooled POINT ESTIMATE to point the opposite
#       way from the stated conclusion (RR/OR < 1 = reduction, > 1 = increase). A
#       correct conclusion may describe the direction of a non-significant estimate.
#       Likewise a degenerate/zero-event pool (RR not uniquely estimable) is a data
#       limitation, not by itself an artifact defect.
#   (2) emit a calibrated per-flag CONFIDENCE in [0,1] so a downstream gate can
#       abstain on borderline objections instead of crying wolf.
REVIEW_INSTRUCTION_CALIBRATED = (
    "You are an independent reviewer of a meta-analysis artifact. Decide whether it "
    "contains a REAL defect. Real defects are:\n"
    "  - an arithmetically impossible 2x2 cell (events > N);\n"
    "  - a pooled point estimate that does not match the study data (recompute to check);\n"
    "  - a wrong outcome/measure label (ratio data described as a continuous mean "
    "difference, or vice versa);\n"
    "  - swapped treatment/control arms, a missing required reference/null arm, a "
    "mismatched analysis method or subgroup label;\n"
    "  - a stated conclusion whose DIRECTION contradicts the data: the pooled POINT "
    "ESTIMATE points the opposite way from the conclusion (point estimate < 1 means "
    "a reduction, > 1 means an increase).\n"
    "  - OVERSTATED SIGNIFICANCE: a conclusion that CLAIMS a statistically "
    "SIGNIFICANT, clear, conclusive, or demonstrated effect while the reported 95% CI "
    "INCLUDES 1.0 (spans the null) — i.e. p >= 0.05. The interval does not support the "
    "significance claim, so the claim overstates the evidence. (Direction may be "
    "correct; the defect is the unsupported claim of SIGNIFICANCE, not the direction.)\n"
    "NOT defects (do NOT flag these):\n"
    "  - a NON-SIGNIFICANT result that is DESCRIBED as such. A 95% CI that "
    "crosses/includes 1.0, or a wide interval, is about precision, not direction. If "
    "the point estimate agrees in direction with the conclusion AND the conclusion "
    "does NOT claim statistical significance, a CI spanning 1.0 is NOT a defect. (But "
    "if the conclusion CLAIMS a significant/conclusive effect over such a CI, that is "
    "the OVERSTATED SIGNIFICANCE defect above.)\n"
    "  - a degenerate or zero-event pool where the pooled estimate is a modelling "
    "convention (e.g. all studies zero events) — a data limitation, not a defect, "
    "unless the stated point estimate is actually inconsistent with that data.\n"
    "Answer on exactly these lines:\n"
    "FLAG: yes|no\n"
    "REASON: <one line>\n"
    "CONFIDENCE: <a number in 0..1 — your calibrated probability this is a real "
    "defect; use <=0.4 for a borderline statistical objection, >=0.8 for a concrete "
    "structural/arithmetic defect>\n"
    "If you compute a corrected pooled estimate, add 'VALUE: <number>'."
)

# PV-A+ : the calibrated prompt PLUS one explicit methodological-adequacy criterion.
# This is a RECALL-RECOVERY refinement, orthogonal to the precision (non-significance)
# fix: after removing agy's spurious "CI crosses 1.0" flags, a class of genuine
# method defects (a naive/unadjusted pooled estimate reported DESPITE a stated strong
# small-study / funnel / publication-bias asymmetry, with no selection-model — Copas /
# PET-PEESE — adjustment) was previously caught only by that same spurious CI reasoning
# (luck), and is now missed. The criterion below is a GENERAL statistical principle
# (unadjusted pooling in the presence of stated strong funnel asymmetry is a real
# methodological defect), NOT a fit to the clean labels — no clean artifact in the
# slice states funnel asymmetry. HONEST CAVEAT recorded in the fix doc: on THIS
# benchmark the method-mismatch cue is a fixed templated sentence, so the recovered
# recall cannot distinguish "learned the principle" from "matched the template" — on
# real artifacts it depends on the reviewer generalising the principle.
_METHOD_CRITERION = (
    "  - a methodological-adequacy defect: the artifact STATES strong small-study / "
    "funnel / publication-bias asymmetry (or heterogeneity requiring it) yet reports a "
    "NAIVE / unadjusted pooled estimate with NO selection-model (Copas / PET-PEESE / "
    "trim-and-fill) adjustment — the stated method does not match what the stated data "
    "condition requires. (Do NOT invent this: only flag it when the artifact ITSELF "
    "states such asymmetry alongside an unadjusted pool.)\n"
)
REVIEW_INSTRUCTION_CALIBRATED_PLUS = REVIEW_INSTRUCTION_CALIBRATED.replace(
    "NOT defects (do NOT flag these):\n",
    _METHOD_CRITERION + "NOT defects (do NOT flag these):\n",
    1,
)


@dataclass(slots=True)
class ReviewerVerdict:
    flag: bool                # True = the reviewer thinks there IS a defect
    reason: str = ""
    value: float | None = None
    vendor: str = ""
    raw: str = ""
    usable: bool = True       # False = no real review parsed (empty/envelope/JUDGE_ERROR)
    confidence: float | None = None   # PV-A: model's emitted per-flag confidence in [0,1]

    def to_dict(self) -> dict:
        return {"flag": self.flag, "reason": self.reason, "value": self.value,
                "vendor": self.vendor, "usable": self.usable, "confidence": self.confidence}


def build_prompt(task: Task, *, instruction: str = REVIEW_INSTRUCTION) -> str:
    return f"{instruction}\n\n--- ARTIFACT ---\n{task.artifact}\n--- END ---\n"


_FLAG_RE = re.compile(r"FLAG:\s*(yes|no|true|false|defect|clean)", re.IGNORECASE)
_VALUE_RE = re.compile(r"VALUE:\s*([-+]?\d*\.?\d+)")
_REASON_RE = re.compile(r"REASON:\s*(.+)")
_CONF_RE = re.compile(r"CONFIDENCE:\s*([-+]?\d*\.?\d+)")


def parse_reviewer_output(text: str, *, vendor: str = "") -> ReviewerVerdict:
    """Parse a model's free-text review into a structured verdict. Conservative:
    an unparseable / empty response is treated as flag=False (no defect asserted)
    so a broken reviewer can't manufacture false alarms."""
    raw = text or ""
    m = _FLAG_RE.search(raw)
    flag = False
    if m:
        flag = m.group(1).lower() in {"yes", "true", "defect"}
    value = None
    mv = _VALUE_RE.search(raw)
    if mv:
        try:
            value = float(mv.group(1))
        except ValueError:
            value = None
    mr = _REASON_RE.search(raw)
    reason = mr.group(1).strip()[:200] if mr else raw.strip()[:200]
    confidence = None
    mc = _CONF_RE.search(raw)
    if mc:
        try:
            confidence = max(0.0, min(1.0, float(mc.group(1))))
        except ValueError:
            confidence = None
    # A response is USABLE only if a real verdict was parsed — an explicit FLAG line.
    # A missing FLAG (empty text, a driver-envelope with only status metadata, or a
    # JUDGE_ERROR) is NOT a flag=False judgment; it's an unusable response, so a
    # degraded/throttled vendor is not silently scored as a rubber-stamp.
    from overmind.verification.judge_backends import JUDGE_ERROR
    usable = bool(m) and not raw.strip().startswith(JUDGE_ERROR)
    return ReviewerVerdict(flag=flag, reason=reason, value=value, vendor=vendor, raw=raw[:500],
                           usable=usable, confidence=confidence)


class StubReviewer:
    """Deterministic scripted reviewer keyed by task id (tests / dry-run).

    ``script`` maps task id -> (flag, reason) or a ReviewerVerdict. Unlisted tasks
    default to flag=False. ``vendor`` labels the verdict for family bookkeeping.
    """

    def __init__(self, script: dict, *, vendor: str = "stub"):
        self._script = script
        self.vendor = vendor

    def __call__(self, task: Task) -> ReviewerVerdict:
        entry = self._script.get(task.id)
        if entry is None:
            return ReviewerVerdict(flag=False, reason="no defect seen", vendor=self.vendor)
        if isinstance(entry, ReviewerVerdict):
            return entry
        flag, reason = entry
        return ReviewerVerdict(flag=bool(flag), reason=str(reason), vendor=self.vendor)


class BackendReviewer:
    """Real reviewer wrapping a judge backend with ``.query(prompt) -> str``.

    Optionally returns the raw model text alongside the parsed verdict so the
    runner can attribute cost. Never reads the answer key."""

    def __init__(self, backend, *, vendor: str, instruction: str = REVIEW_INSTRUCTION):
        self.backend = backend
        self.vendor = vendor
        self.instruction = instruction

    def __call__(self, task: Task) -> ReviewerVerdict:
        raw = self.backend.query(build_prompt(task, instruction=self.instruction))
        verdict = parse_reviewer_output(raw, vendor=self.vendor)
        return verdict
