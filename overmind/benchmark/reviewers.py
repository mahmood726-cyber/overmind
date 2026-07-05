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


@dataclass(slots=True)
class ReviewerVerdict:
    flag: bool                # True = the reviewer thinks there IS a defect
    reason: str = ""
    value: float | None = None
    vendor: str = ""
    raw: str = ""
    usable: bool = True       # False = no real review parsed (empty/envelope/JUDGE_ERROR)

    def to_dict(self) -> dict:
        return {"flag": self.flag, "reason": self.reason, "value": self.value,
                "vendor": self.vendor, "usable": self.usable}


def build_prompt(task: Task) -> str:
    return f"{REVIEW_INSTRUCTION}\n\n--- ARTIFACT ---\n{task.artifact}\n--- END ---\n"


_FLAG_RE = re.compile(r"FLAG:\s*(yes|no|true|false|defect|clean)", re.IGNORECASE)
_VALUE_RE = re.compile(r"VALUE:\s*([-+]?\d*\.?\d+)")
_REASON_RE = re.compile(r"REASON:\s*(.+)")


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
    # A response is USABLE only if a real verdict was parsed — an explicit FLAG line.
    # A missing FLAG (empty text, a driver-envelope with only status metadata, or a
    # JUDGE_ERROR) is NOT a flag=False judgment; it's an unusable response, so a
    # degraded/throttled vendor is not silently scored as a rubber-stamp.
    from overmind.verification.judge_backends import JUDGE_ERROR
    usable = bool(m) and not raw.strip().startswith(JUDGE_ERROR)
    return ReviewerVerdict(flag=flag, reason=reason, value=value, vendor=vendor, raw=raw[:500], usable=usable)


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

    def __init__(self, backend, *, vendor: str):
        self.backend = backend
        self.vendor = vendor

    def __call__(self, task: Task) -> ReviewerVerdict:
        raw = self.backend.query(build_prompt(task))
        verdict = parse_reviewer_output(raw, vendor=self.vendor)
        return verdict
