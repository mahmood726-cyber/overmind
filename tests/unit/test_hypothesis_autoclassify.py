"""Trip-tests for auto-classification of confirms_hypothesis.

The recovery-multiplier lane softened a result toward Mahmood TWICE. The
anti-sycophancy gate must NOT depend on the emitting lane remembering to declare
``confirms_hypothesis`` — a hypothesis registered once (with a pre-registered
refutation) must force the cross-family requirement on any matching headline,
whether or not the lane opted in. Every gate here has a test that trips it.
"""
from __future__ import annotations

import pytest

from overmind.factstore import FactStore, SycophancyGateError


def _reg(fs, **over):
    kw = dict(
        slug="abstract-first",
        statement="Abstract-first reaches ~80% of gold trials without the paywall",
        key_patterns=["coverage.union*"],
        refutation_criterion="union coverage < 0.70 on the gold set refutes it",
        direction={"op": ">=", "threshold": 0.70},
    )
    kw.update(over)
    fs.register_hypothesis(kw["slug"], statement=kw["statement"],
                           key_patterns=kw["key_patterns"],
                           refutation_criterion=kw["refutation_criterion"],
                           direction=kw["direction"])


# --- THE gate: a matching headline is auto-flagged even when the lane forgets ---

def test_undeclared_confirming_headline_is_auto_classified():
    fs = FactStore()
    _reg(fs)
    # lane emits a confirming number WITHOUT declaring confirms_hypothesis
    fid = fs.record_real("coverage.union", 0.80, source="gold44", lane="cov-lane")
    assert fs.get(fid).confirms_hypothesis is True
    assert fs.get(fid).refutation_criterion  # inherited the pre-registered one


def test_auto_classified_headline_needs_two_families_to_verify():
    """TRIP: the auto-classified confirming headline cannot be verified with a
    single vendor family — the lane never opted in, the gate fires anyway."""
    fs = FactStore()
    _reg(fs)
    fid = fs.record_real("coverage.union", 0.80, source="gold44", lane="cov-lane")
    with pytest.raises(SycophancyGateError):
        fs.verify(fid, families=["openai"])           # one family -> blocked
    fs.verify(fid, families=["openai", "google"])     # two distinct -> ok
    assert fs.consume_verified("coverage.union") == 0.80


def test_same_family_panel_is_refused_for_auto_classified():
    """Two reviewers of the SAME family is not cross-family review."""
    fs = FactStore()
    _reg(fs)
    fid = fs.record_real("coverage.union", 0.80, source="gold44", lane="cov-lane")
    with pytest.raises(SycophancyGateError):
        fs.verify(fid, families=["openai", "openai"])  # collapses to one family


def test_refuting_value_is_not_auto_confirmed():
    """A value BELOW the threshold does not confirm the hypothesis, so it is not
    force-flagged (a refuting result must not be mislabeled as confirming)."""
    fs = FactStore()
    _reg(fs)
    fid = fs.record_real("coverage.union", 0.50, source="gold44", lane="cov-lane")
    assert fs.get(fid).confirms_hypothesis is False
    fs.verify(fid, families=["openai"])  # not confirming -> single family fine
    assert fs.consume_verified("coverage.union") == 0.50


def test_non_matching_key_is_untouched():
    fs = FactStore()
    _reg(fs)
    fid = fs.record_real("coverage.hard_residual", 0.20, source="gold44", lane="cov-lane")
    assert fs.get(fid).confirms_hypothesis is False


def test_direction_field_form_matches_dict_value():
    fs = FactStore()
    _reg(fs, slug="se-claim", key_patterns=["*.se.headline*"],
         direction={"op": ">=", "threshold": 0.9, "field": "se"})
    fid = fs.record_real("TB.se.headline", {"se": 0.91, "k": 4},
                         source="pool", lane="x")
    assert fs.get(fid).confirms_hypothesis is True


def test_hypothesis_without_refutation_is_rejected():
    """A hypothesis you cannot refute is not admissible."""
    fs = FactStore()
    with pytest.raises(SycophancyGateError):
        fs.register_hypothesis("bad", statement="x", key_patterns=["k*"],
                               refutation_criterion="   ")


def test_registry_survives_reopen(tmp_path):
    """Hypotheses persist to disk so the auto-classify gate survives a restart."""
    db = str(tmp_path / "h.db")
    fs = FactStore(db)
    _reg(fs)
    fs.close()
    fs2 = FactStore(db)
    fid = fs2.record_real("coverage.union", 0.80, source="g", lane="l")
    assert fs2.get(fid).confirms_hypothesis is True
    with pytest.raises(SycophancyGateError):
        fs2.verify(fid, families=["openai"])
