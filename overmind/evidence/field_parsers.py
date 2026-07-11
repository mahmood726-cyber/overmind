"""Two heterogeneous, deterministic effect-field parsers.

These exist to *exercise* the calibrated-extraction seam
(:mod:`overmind.evidence.calibrated_extraction`) with two genuinely different
strategies, so the quorum layer has real agreement/disagreement to adjudicate —
without any LLM call (reproducible, zero-cost, model-free). They are also a
useful deterministic floor extractor in their own right.

The seam is model-agnostic: in production these two parsers can be swapped for
two heterogeneous LLM extractions; the adjudication logic is identical.

* :func:`parse_labeled` — strict "labelled value" reader: a measure token
  immediately bound to a number (``RR: 0.87``, ``HR = 0.85``, ``odds ratio of
  1.2``). High precision, abstains when the binding is not explicit.
* :func:`parse_proximity` — a measure keyword plus the nearest *plausible ratio*
  number in a short window, rejecting numbers that read as counts/ages/percents.
  Higher recall, lower precision.

Both return ``(measure_value, measure_type_value)`` as
:class:`~overmind.evidence.calibrated_extraction.ExtractedValue` with a source
span. A declined field is ``ExtractedValue(None, 0.0)`` — a first-class "not
present", never a fabricated default.
"""
from __future__ import annotations

import re

from overmind.evidence.calibrated_extraction import ExtractedValue

# measure token -> canonical type
_MEASURE_TOKENS = {
    "rr": "RR", "risk ratio": "RR", "relative risk": "RR",
    "or": "OR", "odds ratio": "OR",
    "hr": "HR", "hazard ratio": "HR",
}
# Plausible range for an effect ratio; outside this a number is almost certainly
# a count / age / sample size, not an effect estimate.
_RATIO_LO, _RATIO_HI = 0.01, 100.0
# Words that mark a nearby number as NOT an effect estimate.
_NEGATION = re.compile(r"\bnot\s+(calculable|estimable|reported|available|significant|reached)\b", re.I)
_COUNTISH = re.compile(r"\b(patients?|subjects?|participants?|enrolled|aged?|years?|n\s*=)\b", re.I)

_LABEL_RX = re.compile(
    r"\b(risk ratio|relative risk|odds ratio|hazard ratio|RR|OR|HR)\b"
    r"[\s:,=]*(?:of|was|is)?[\s:,=]*"      # connector: 'of'/'was'/'is'/':'/','/'=' or space
    r"(\d+\.\d+|\d+)",
    re.I,
)
_KEYWORD_RX = re.compile(r"\b(risk ratio|relative risk|odds ratio|hazard ratio|RR|OR|HR)\b", re.I)
_NUM_RX = re.compile(r"\d+\.\d+|\d+")


def _canon(tok: str) -> str | None:
    return _MEASURE_TOKENS.get(tok.strip().lower())


def _distinct_labeled_values(text: str) -> set[float]:
    """Distinct plausible-ratio values that are DIRECTLY bound to a measure token.

    Used to detect ambiguous source text (two different labelled effect estimates,
    e.g. 'RR 0.9 in ITT, RR 0.85 in PP') where a single extracted value would be a
    guess — the correct action there is to abstain, not to pick the first one. CI
    bounds inside parentheses are not measure-labelled, so they don't count.
    """
    vals: set[float] = set()
    for _tok, num in _LABEL_RX.findall(text):
        try:
            v = float(num)
        except ValueError:
            continue
        if _RATIO_LO <= v <= _RATIO_HI:
            vals.add(round(v, 4))
    return vals


def parse_labeled(text: str) -> tuple[ExtractedValue, ExtractedValue]:
    """Strict labelled-value parser. High precision, abstains on weak binding."""
    if not text or _NEGATION.search(text):
        return ExtractedValue(None, 0.0, model="labeled"), ExtractedValue(None, 0.0, model="labeled")
    if len(_distinct_labeled_values(text)) > 1:   # ambiguous: >1 labelled estimate -> abstain value
        m0 = _KEYWORD_RX.search(text)
        return ExtractedValue(None, 0.0, model="labeled"), ExtractedValue(
            _canon(m0.group(1)) if m0 else None, 0.4 if m0 else 0.0, m0.group(0) if m0 else None, "labeled")
    m = _LABEL_RX.search(text)
    if not m:
        return ExtractedValue(None, 0.0, model="labeled"), ExtractedValue(None, 0.0, model="labeled")
    mtype = _canon(m.group(1))
    try:
        val = float(m.group(2))
    except ValueError:
        val = None
    if val is None or not (_RATIO_LO <= val <= _RATIO_HI):
        return ExtractedValue(None, 0.0, model="labeled"), ExtractedValue(mtype, 0.4, m.group(0), "labeled")
    span = m.group(0)
    return (ExtractedValue(val, 0.9, span, "labeled"),
            ExtractedValue(mtype, 0.9, span, "labeled"))


def parse_proximity(text: str) -> tuple[ExtractedValue, ExtractedValue]:
    """Keyword + nearest-plausible-ratio parser. Higher recall, lower precision."""
    if not text or _NEGATION.search(text):
        return ExtractedValue(None, 0.0, model="proximity"), ExtractedValue(None, 0.0, model="proximity")
    if len(_distinct_labeled_values(text)) > 1:   # ambiguous: >1 labelled estimate -> abstain value
        m0 = _KEYWORD_RX.search(text)
        return ExtractedValue(None, 0.0, model="proximity"), ExtractedValue(
            _canon(m0.group(1)) if m0 else None, 0.5 if m0 else 0.0, m0.group(0) if m0 else None, "proximity")
    km = _KEYWORD_RX.search(text)
    if not km:
        return ExtractedValue(None, 0.0, model="proximity"), ExtractedValue(None, 0.0, model="proximity")
    mtype = _canon(km.group(1))
    # search a window after the keyword for the first plausible ratio number
    window = text[km.end():km.end() + 40]
    best = None
    for nm in _NUM_RX.finditer(window):
        # skip numbers that read as counts/ages (a countish word right before)
        pre = window[max(0, nm.start() - 14):nm.start()]
        if _COUNTISH.search(pre):
            continue
        try:
            v = float(nm.group(0))
        except ValueError:
            continue
        if _RATIO_LO <= v <= _RATIO_HI:
            # confidence decays with the gap between the measure token and the
            # number — a tightly-bound value ("RR 0.87") is more reliable than a
            # distant one ("RR ... 0.87"). A legitimate reliability signal, and it
            # gives the conformal layer a graded score to threshold on.
            gap = nm.start()
            conf = max(0.45, min(0.8, 0.8 - 0.03 * gap))
            best = (v, km.group(0) + window[:nm.end()], conf)
            break
    if best is None:
        return ExtractedValue(None, 0.0, model="proximity"), ExtractedValue(mtype, 0.5, km.group(0), "proximity")
    return (ExtractedValue(best[0], best[2], best[1], "proximity"),
            ExtractedValue(mtype, 0.7, km.group(0), "proximity"))
