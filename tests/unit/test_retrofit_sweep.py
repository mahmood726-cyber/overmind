"""Part IV — the retrofit: narrow the world-claim denominator, mark UNVERIFIED.

Part III reported an ugly range (36.4%-89.5% of shipped numbers would fail the
gate) but did NOT separate world-claims (facts about a trial/effect that need a
locator) from internals (test counts, timings, versions — which need none). These
tests pin the classifier and the on-screen UNVERIFIED marker.
"""
from __future__ import annotations

import pytest

from overmind.gates.sweep import (
    classify_number, mark_unverified, sweep_text, _destination_bucket,
)
from overmind.gates.resolver import LocatorResolver, Resolution


class _NullResolver(LocatorResolver):
    def __init__(self):
        super().__init__(aact_path=None)
    def resolve(self, locator, claimed_value=None):
        return Resolution(False, None, "null", reason="offline")


# --- the classifier: world-claim vs internal ----------------------------------

@pytest.mark.parametrize("sentence", [
    "pooled RR 0.63 (95% CI 0.41-0.97) across 12 trials",
    "sensitivity was 85.8% at the primary endpoint",
    "mortality fell to 9.6% in the treatment arm",
    "recall reached 33.7% of poolable trials",
    "HR=0.921 for the intervention",
])
def test_world_claims_are_flagged_world(sentence):
    assert classify_number(sentence) == "world"


@pytest.mark.parametrize("sentence", [
    "145 tests green in 3.60s",
    "scanned 68 files, 18 open holes",
    "python 3.13, duckdb 0.9",
    "the stick was 1.22GB and took 5.5s",
    "commit 108d2af, branch feat/shared-fact-store",
])
def test_internal_numbers_are_flagged_internal(sentence):
    assert classify_number(sentence) == "internal"


def test_ratio_is_always_world_even_amid_code_words():
    # an effect ratio wins even if the sentence also has 'test'/'file' vocabulary
    assert classify_number("the test file reports RR=1.21 for discontinuation") == "world"


@pytest.mark.parametrize("sentence", [
    "LDL-C fell by 38.1% after 12 weeks.",
    "HbA1c decreased by 0.43 at week 24.",
    "Serious adverse events occurred in 14%.",
    "The event rate was 12% in the intervention group.",
    "The improvement was 0.55 on the scale.",       # 'improv' -> world
])
def test_codex_round4_false_negatives_are_now_world(sentence):
    """Codex round-4: these clinical claims were classified 'internal' and escaped
    UNVERIFIED marking. Positively matched by the EXPANDED world-token list (not a
    blanket default flip, which over-marked every bare number to 93%)."""
    assert classify_number(sentence) == "world"


@pytest.mark.parametrize("sentence", [
    "eGFR test result changed by 12%.",
    "CRP test result changed by 12%.",
    "NT-proBNP test result changed by 12%.",
])
def test_codex_round5_lab_marker_false_negatives_are_world(sentence):
    """Codex round-5: lab markers described as 'test result' were caught by the internal
    'test' token. Named markers make world win (checked before internal)."""
    assert classify_number(sentence) == "world"


@pytest.mark.parametrize("sentence", [
    "WOMAC pain test score was 12%.",
    "positive tuberculin skin test was 12%.",
    "6-minute walk test completion rate was 12%.",
])
def test_codex_round6_clinical_test_names_not_internal(sentence):
    """Codex round-6: clinical instruments ('WOMAC ... test', 'skin test', 'walk test')
    were forced to 'internal' by bare 'test'. Now 'test' needs a code context, so these
    fall to 'ambiguous' — which IS marked on screen (not silently kept)."""
    assert classify_number(sentence) != "internal"


@pytest.mark.parametrize("sentence", [
    "The figure was 0.42 in the middle column.",
    "It came to 12.5% overall.",
])
def test_vocabulary_less_numbers_are_ambiguous(sentence):
    """A claim-shaped number with NEITHER world nor internal vocabulary is 'ambiguous'
    — reported as its own class so the world-claim denominator is a RANGE, not a
    default-driven point. (mark_unverified still marks these on screen, conservatively.)"""
    assert classify_number(sentence) == "ambiguous"


def test_ambiguous_is_marked_but_counted_separately():
    text = "The figure was 0.42 in the middle column."
    out, n = mark_unverified(text)
    assert n == 1 and "UNVERIFIED" in out        # marked on screen (conservative)
    r = sweep_text(text, "d.md", _NullResolver())
    assert r.ambiguous_numbers == 1 and r.world_numbers == 0   # but not counted as world


# --- the narrowed denominator on a synthetic doc ------------------------------

def test_sweep_separates_world_from_internal():
    text = (
        "The pooled risk ratio was 0.63 across trials.\n"   # world, no id -> unverified
        "In NCT04336189 sensitivity reached 0.85 overall.\n"  # world, HAS id -> located
        "The suite test pass rate was 0.99 this run.\n"     # internal (test/pass/run)
        "Coverage reached 33.7% of trials.\n"               # world, no id -> unverified
    )
    r = sweep_text(text, "demo.md", _NullResolver())
    assert r.world_numbers == 3           # 0.63, 0.85, 33.7%
    assert r.internal_numbers == 1        # the 0.99 test pass rate
    assert r.world_located == 1           # the NCT-bearing one
    assert r.world_unverified == 2        # the two naked world-claims


# --- the on-screen UNVERIFIED marker ------------------------------------------

def test_mark_unverified_marks_naked_world_claims():
    text = "The pooled RR was 0.63 across trials.\nSee NCT04336189 arm count 3."
    out, n = mark_unverified(text)
    assert n == 1                                  # only the naked world-claim line
    assert "UNVERIFIED" in out.splitlines()[0]     # the RR line got marked
    assert "UNVERIFIED" not in out.splitlines()[1] # the NCT line did not


def test_mark_unverified_leaves_internal_numbers_alone():
    text = "145 tests passed in 3.6s.\nScanned 68 files."
    out, n = mark_unverified(text)
    assert n == 0 and "UNVERIFIED" not in out


def test_mark_unverified_is_idempotent():
    text = "Recall was 33.7% of trials."
    once, n1 = mark_unverified(text)
    twice, n2 = mark_unverified(once)
    assert n1 == 1 and n2 == 0 and once == twice   # second pass marks nothing new


def test_mark_unverified_html_mode():
    text = "Sensitivity 85.8% at endpoint."
    out, n = mark_unverified(text, html=True)
    assert n == 1 and "overmind-unverified" in out


# --- destination buckets (Kampala priority order) -----------------------------

def test_destination_buckets():
    assert _destination_bucket("F:/rapidmeta-x/students.html") == "app_page"
    assert _destination_bucket("C:/Projects/tuesday-slides.md") == "slides"
    assert _destination_bucket("C:/Projects/REPORT.md") == "deliverable"
    assert _destination_bucket("app/dashboard.ipynb") == "app_page"
