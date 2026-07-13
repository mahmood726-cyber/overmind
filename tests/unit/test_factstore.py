"""Shared fact-store trip-tests (architecture fix #1).

Every gate has a test that TRIPS it: it constructs the exact bad path (a synthetic
number consumed as real, an unverified partial emitted as complete, two lanes
disagreeing, a confirming headline verified without cross-family review) and
asserts the store FAILS LOUD. A gate that cannot fail is not a gate.
"""
from __future__ import annotations

import pytest

from overmind.factstore import (
    FactStore, Provenance, Status,
    SyntheticFactError, UnverifiedFactError, ContradictedFactError,
    SycophancyGateError, NoSuchFactError,
)


# --- THE DTA70 failure: a synthetic number must never be consumed as real -------

def test_dta70_fake_tb_number_is_blocked_transitively():
    """TRIP TEST (the exact failure): DTA70 is synthetic; a lane derives the TB
    headline from it; a third lane tries to consume it as a real result. The
    synthetic flag propagated across BOTH lane boundaries and consume FAILS LOUD."""
    fs = FactStore()
    # lane A: the raw DTA70 figure — synthetic
    raw = fs.record_synthetic("TB.DTA.sensitivity", 0.858, source="DTA70:tb", lane="dta-lane")
    # lane B: derives the headline from it, unaware of the origin
    headline = fs.derive("TB.DTA.headline", {"Se": 0.858, "Sp": 0.978, "k": 17},
                         from_ids=[raw], source="pool_calc", lane="synthesis-lane")
    # the derived fact is SYNTHETIC transitively, even though lane B declared REAL
    assert fs.get(headline).provenance == Provenance.SYNTHETIC
    # lane C (the slide): consuming it as a verified real number must raise
    with pytest.raises(SyntheticFactError) as ei:
        fs.consume_verified("TB.DTA.headline")
    assert "DTA70" in str(ei.value) or "SYNTHETIC" in str(ei.value)


def test_synthetic_cannot_be_verified_real():
    """A synthetic fact can never be marked verified — closes the loophole of
    'verifying' the fake number to make it consumable."""
    fs = FactStore()
    fid = fs.record_synthetic("x", 1.0, source="DTA70", lane="l")
    with pytest.raises(SyntheticFactError):
        fs.verify(fid, families=["openai", "google"])


def test_transitive_synthetic_through_deep_chain():
    fs = FactStore()
    s = fs.record_synthetic("a", 1.0, source="DTA70", lane="l")
    b = fs.derive("b", 2.0, from_ids=[s], source="calc", lane="l")
    r = fs.record_real("c", 3.0, source="PMID:9", lane="l")
    # c is real, but a fact derived from BOTH b(synthetic) and c(real) is synthetic
    d = fs.derive("d", 5.0, from_ids=[b, r], source="calc", lane="l")
    assert fs.get(d).provenance == Provenance.SYNTHETIC


# --- unverified / verified consumption gate -------------------------------------

def test_unverified_real_number_is_blocked():
    """A real but UNVERIFIED number (a partial run) must never emit as complete."""
    fs = FactStore()
    fs.record_real("m.effect", 0.72, source="PMID:1", lane="l")
    with pytest.raises(UnverifiedFactError):
        fs.consume_verified("m.effect")


def test_verified_real_number_is_consumable():
    fs = FactStore()
    fid = fs.record_real("m.effect", 0.72, source="PMID:1", lane="l")
    fs.verify(fid, families=["openai", "google"], reviewer="panel")
    assert fs.consume_verified("m.effect") == 0.72


def test_missing_key_raises():
    fs = FactStore()
    with pytest.raises(NoSuchFactError):
        fs.consume_verified("nope")


# --- contradiction: two lanes, two values, neither usable -----------------------

def test_two_lanes_disagree_flags_both_and_blocks():
    """TRIP TEST: two lanes assert different values for one fact -> BOTH flagged,
    neither usable until adjudicated. Silence is not agreement."""
    fs = FactStore()
    a = fs.record_real("hr", 0.80, source="laneA", lane="A")
    b = fs.record_real("hr", 0.55, source="laneB", lane="B")
    assert fs.get(a).status == Status.CONTRADICTED
    assert fs.get(b).status == Status.CONTRADICTED
    # consuming the key is blocked while unadjudicated
    with pytest.raises(ContradictedFactError):
        fs.consume_verified("hr")
    # and a contradicted fact cannot even be verified until adjudicated (a gate)
    with pytest.raises(ContradictedFactError):
        fs.verify(a, families=["openai", "google"])


def test_adjudication_unblocks_the_winner():
    fs = FactStore()
    a = fs.record_real("hr", 0.80, source="laneA", lane="A")
    b = fs.record_real("hr", 0.55, source="laneB", lane="B")
    fs.adjudicate(winner_id=a, loser_ids=[b], reviewer="human", detail="A cross-checked to source")
    fs.verify(a, families=["openai", "google"])
    assert fs.consume_verified("hr") == 0.80
    assert fs.get(b).status == Status.REFUTED


def test_agreeing_values_are_not_a_contradiction():
    fs = FactStore()
    fs.record_real("hr", 0.800000, source="A", lane="A")
    b = fs.record_real("hr", 0.800000001, source="B", lane="B")  # within tol
    assert fs.get(b).status != Status.CONTRADICTED


# --- anti-sycophancy: confirming headlines need cross-family review -------------

def test_confirming_headline_requires_preregistered_refutation():
    """TRIP TEST (#4): a hypothesis-confirming fact with NO pre-registered
    refutation criterion is refused at assert time — it cannot be added post-hoc."""
    fs = FactStore()
    with pytest.raises(SycophancyGateError):
        fs.record_real("recovery.multiplier", 2.5, source="calc", lane="l",
                       confirms_hypothesis=True, hypothesis="recovery multiplier is large")


def test_confirming_headline_needs_two_distinct_families_to_verify():
    """TRIP TEST (#4): a confirming headline cannot be verified by a same-family
    panel — it needs >= 2 DISTINCT vendor families (cross-family adversarial)."""
    fs = FactStore()
    fid = fs.record_real(
        "recovery.multiplier", 2.5, source="calc", lane="l",
        confirms_hypothesis=True, hypothesis="recovery multiplier is large",
        refutation_criterion="refuted if denominator-correct multiplier < 1.5")
    # single family (two claude seats) == a same-family panel -> refused
    with pytest.raises(SycophancyGateError):
        fs.verify(fid, families=["anthropic"])
    with pytest.raises(SycophancyGateError):
        fs.verify(fid, families=["anthropic", "anthropic"])
    # two distinct families -> allowed
    fs.verify(fid, families=["openai", "google"], reviewer="panel")
    assert fs.consume_verified("recovery.multiplier") == 2.5


def test_non_confirming_fact_verifies_normally():
    fs = FactStore()
    fid = fs.record_real("x", 1.0, source="s", lane="l")
    fs.verify(fid, families=["openai"])   # ordinary fact, no sycophancy gate
    assert fs.consume_verified("x") == 1.0


def test_reslice_rescue_is_flagged_and_recorded():
    fs = FactStore()
    fid = fs.record_real("y", 1.0, source="s", lane="l")
    fs.flag_reslice(fid, reviewer="auditor", detail="p-value only after dropping 3 studies")
    assert any(e["kind"] == "reslice_flag" for e in fs.get(fid).events)


# --- resumability / checkpointing (kill mid-run, reopen, no corruption) ---------

def test_resumable_from_disk_after_reopen(tmp_path):
    """TRIP TEST (#2): facts + status survive a close/reopen (a PC restart). A
    partial (unverified) fact stays unverified and still cannot be consumed."""
    path = tmp_path / "facts.db"
    fs = FactStore(path)
    verified = fs.record_real("done.effect", 0.63, source="PMID:1", lane="l")
    fs.verify(verified, families=["openai", "google"])
    fs.record_real("partial.effect", 0.10, source="PMID:2", lane="l")  # never verified
    fs.close()

    # reopen — simulate resume after a restart
    fs2 = FactStore(path)
    assert fs2.consume_verified("done.effect") == 0.63     # verified survived
    with pytest.raises(UnverifiedFactError):
        fs2.consume_verified("partial.effect")             # partial still blocked
    # provenance + events intact
    assert fs2.get(verified).status == Status.VERIFIED
    fs2.close()


def test_launder_then_summarise_is_blocked(tmp_path):
    """THE handoff trip-test (context-window laundering). Lane A seeds a synthetic
    fixture; lane B derives from it (edge path); lane C READS it then re-emits the
    bare value as a FRESH ROOT fact with NO declared lineage (the laundering path
    that broke the DAG). The summary gate MUST block BOTH. If this passes silently,
    the store does not work."""
    path = tmp_path / "launder.db"
    # lane A: the synthetic DTA70 figure
    a = FactStore(path, session_lane="lane-A")
    fixture = a.record_synthetic("TB.DTA.sens", 0.858, source="DTA70:tb", lane="lane-A")
    a.close()

    # lane B: derives from it via a fact edge -> transitively synthetic (edge layer)
    b = FactStore(path, session_lane="lane-B")
    edge = b.derive("TB.headline.edge", 0.858, from_ids=[fixture],
                    source="pool", lane="lane-B")
    assert b.get(edge).provenance == Provenance.SYNTHETIC
    b.close()

    # lane C: READS the synthetic fixture (context contaminated), then writes a
    # BRAND-NEW ROOT fact with NO parents, declaring it real (the launder).
    c = FactStore(path, session_lane="lane-C")
    _ = c.get(fixture)                                  # <-- rehydrate-on-read taints lane-C
    laundered = c.assert_fact("TB.headline.laundered", 0.858,
                              provenance=Provenance.REAL,   # lane CLAIMS real...
                              source_locator="my summary", lane="lane-C")  # ...no lineage
    assert c.get(laundered).provenance == Provenance.SYNTHETIC   # ...but forced synthetic
    c.close()

    # the summary gate blocks BOTH the edge-derived and the laundered headline
    s = FactStore(path)
    with pytest.raises(SyntheticFactError):
        s.consume_verified("TB.headline.edge")
    with pytest.raises(SyntheticFactError):
        s.consume_verified("TB.headline.laundered")
    s.close()


def test_value_taint_catches_copy_without_reading(tmp_path):
    """Even a lane that never READ the fixture, but copies the specific synthetic
    NUMBER (with rounding), is force-tainted by the value-taint set."""
    path = tmp_path / "vt.db"
    a = FactStore(path, session_lane="lane-A")
    a.record_synthetic("x", 0.858, source="DTA70", lane="lane-A")
    a.close()

    # a different, un-contaminated lane copies the number (rounded) with fresh lineage
    d = FactStore(path, session_lane="lane-D")
    fid = d.record_real("y", 0.86, source="typed-by-hand", lane="lane-D")  # 0.858 -> 0.86
    assert d.get(fid).provenance == Provenance.SYNTHETIC
    d.close()


def test_clean_lane_non_interference_stays_real(tmp_path):
    """Non-interference: a lane that NEVER read synthetic data and does NOT reuse a
    tainted value produces REAL, consumable facts — the store is not sticky-by-default
    (else lanes route around it). Only contamination taints."""
    path = tmp_path / "clean.db"
    a = FactStore(path, session_lane="lane-A")
    a.record_synthetic("x", 0.858, source="DTA70", lane="lane-A")
    a.close()

    clean = FactStore(path, session_lane="clean-lane")   # never reads the synthetic fact
    fid = clean.record_real("real.effect", 0.63, source="PMID:5", lane="clean-lane")
    clean.verify(fid, families=["openai", "google"])
    assert clean.consume_verified("real.effect") == 0.63   # clean output, verified
    assert "clean-lane" not in clean.tainted_lanes()
    clean.close()


def test_tainted_lane_persists_across_reopen(tmp_path):
    """Cross-session persistence: a lane tainted in one session stays tainted after a
    restart (a contaminated context can't be laundered by reopening the store)."""
    path = tmp_path / "persist.db"
    a = FactStore(path, session_lane="lane-A")
    fx = a.record_synthetic("x", 0.858, source="DTA70", lane="lane-A")
    a.close()
    c1 = FactStore(path, session_lane="lane-C")
    c1.get(fx)                     # taint lane-C
    c1.close()
    # new process/session, same lane id -> still tainted
    c2 = FactStore(path, session_lane="lane-C")
    fid = c2.record_real("fresh", 0.5, source="s", lane="lane-C")
    assert c2.get(fid).provenance == Provenance.SYNTHETIC
    c2.close()


def test_open_shared_resolves_env_path(tmp_path, monkeypatch):
    """The shared store is one conventional location so every lane joins the SAME
    store with one line — no per-lane private notebook."""
    from overmind.factstore import open_shared
    db = tmp_path / "sub" / "shared.db"
    monkeypatch.setenv("OVERMIND_FACTSTORE", str(db))
    a = open_shared()
    fid = a.record_real("k", 1.0, source="s", lane="A")
    a.verify(fid, families=["openai", "google"])
    a.close()
    # a DIFFERENT lane opening the shared store sees lane A's verified fact
    b = open_shared()
    assert b.consume_verified("k") == 1.0
    b.close()


def test_append_only_value_is_never_mutated(tmp_path):
    """A fact's value/provenance are immutable — verification is a separate event,
    so the audit history is never rewritten."""
    fs = FactStore(tmp_path / "f.db")
    fid = fs.record_synthetic("z", 9.0, source="DTA70", lane="l")
    before = fs.get(fid)
    fs.refute(fid, reviewer="x")
    after = fs.get(fid)
    assert before.value == after.value == 9.0
    assert after.provenance == Provenance.SYNTHETIC   # unchanged
    assert after.status == Status.REFUTED             # only the folded status moved
