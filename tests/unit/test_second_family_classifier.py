"""Part V Fix #4 — shrink the 36.1% ambiguous band with a DIFFERENT-FAMILY classifier.

The regex "ambiguous" band is same-family (one author's vocabulary). A different family
(Codex/GPT-5 here) decorrelates it. This proves the wiring:
  * a regex-ambiguous sentence WITH a cached different-family world/internal verdict is
    reclassified (the band shrinks);
  * a regex-ambiguous sentence the second family also could not decide — or never saw —
    STAYS ambiguous and is still marked on screen (bounded + visible, not silently kept).
The measured shrink on the live 80-sentence sample is asserted from the shipped verdict
file so a regression that empties or corrupts it turns the suite red.
"""
from __future__ import annotations

import json
import os

from overmind.gates import sweep
from overmind.gates.sweep import classify_number, classify_with_second_family


def test_second_family_reclassifies_a_cached_ambiguous_sentence(monkeypatch):
    monkeypatch.setattr(sweep, "_SECOND_FAMILY",
                        {"the widget rendered in 4 columns": "internal",
                         "response seen in 4 of the treated group": "world"})
    # both are regex-ambiguous (no world/internal vocabulary), reclassified by 2nd family
    assert classify_number("the widget rendered in 4 columns") == "ambiguous"
    assert classify_with_second_family("the widget rendered in 4 columns") == "internal"
    assert classify_with_second_family("response seen in 4 of the treated group") == "world"


def test_unseen_ambiguous_stays_ambiguous_and_visible(monkeypatch):
    monkeypatch.setattr(sweep, "_SECOND_FAMILY", {})
    s = "the marker settled near 0.42 midway"
    assert classify_number(s) == "ambiguous"
    assert classify_with_second_family(s) == "ambiguous"   # stays ambiguous -> still marked


def test_second_family_never_overrides_a_decisive_regex_verdict(monkeypatch):
    # a WORLD sentence is not demoted even if a stray verdict says internal
    monkeypatch.setattr(sweep, "_SECOND_FAMILY",
                        {"pooled RR was 0.67 across trials": "internal"})
    assert classify_number("pooled RR was 0.67 across trials") == "world"
    assert classify_with_second_family("pooled RR was 0.67 across trials") == "world"


def test_shipped_verdict_file_shrinks_the_band():
    """The live measurement, pinned: the shipped Codex/GPT-5 verdicts resolve the large
    majority of the sampled ambiguous band, leaving a small residual still ambiguous."""
    path = os.path.join(os.path.dirname(sweep.__file__), "data", "second_family_verdicts.json")
    if not os.path.exists(path):
        import pytest
        pytest.skip("second-family verdict file not present")
    data = json.load(open(path, encoding="utf-8"))
    verdicts = data["verdicts"]
    n = len(verdicts)
    resolved = sum(1 for v in verdicts.values() if v in ("world", "internal"))
    still = sum(1 for v in verdicts.values() if v == "ambiguous")
    assert n >= 50                                  # a real sample, not a token file
    assert resolved / n >= 0.70                     # the band shrinks by >=70%
    assert resolved + still == n                    # every verdict is one of the three
    assert "GPT-5" in data.get("classifier", "") or "gemini" in data.get("classifier", "").lower()
