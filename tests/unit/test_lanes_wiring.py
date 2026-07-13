"""Trip-tests for the lane-adoption layer — the wiring that makes the store protect
something. A gate nothing calls protects nothing; these tests call it.

The flagship assertion is Mahmood's question: could a fabricated figure still reach
a slide? Answered by running the Tuesday demo lane and the known-bad artefacts in
ONE store and asserting the real numbers pass while every fabrication is blocked.
"""
from __future__ import annotations

import pytest

from overmind.factstore import (
    FactStore, open_shared, SyntheticFactError, FactStoreError,
)
from overmind.factstore.lanes import tuesday_demo, known_bad


# --- Tuesday demo: every on-screen number survives the gate --------------------

def test_every_tuesday_demo_number_passes_consume(tmp_path):
    fs = FactStore(str(tmp_path / "demo.db"), session_lane=tuesday_demo.LANE)
    tuesday_demo.wire(fs)
    rows = tuesday_demo.report(fs)
    failed = [r["key"] for r in rows if not r["ok"]]
    assert not failed, f"demo numbers that failed consume_verified: {failed}"
    assert len(rows) == len(tuesday_demo.DEMO_NUMBERS)


def test_coverage_claim_is_auto_gated_by_two_families(tmp_path):
    """The ~80% coverage claim is a hypothesis-confirming headline; the demo lane
    never declares it, but wiring registers Mahmood's hypotheses so it is auto-
    classified and REQUIRES two families. Verifying it with one family must fail."""
    fs = FactStore(str(tmp_path / "cov.db"), session_lane=tuesday_demo.LANE)
    tuesday_demo.hypotheses.register_all(fs)
    fid = fs.record_real("coverage.union", 0.80, source="gold44", lane=tuesday_demo.LANE)
    assert fs.get(fid).confirms_hypothesis is True
    with pytest.raises(FactStoreError):
        fs.verify(fid, families=["openai"])


# --- Known-bad: every fabrication is blocked -----------------------------------

def test_every_known_bad_artefact_is_blocked(tmp_path):
    fs = FactStore(str(tmp_path / "kb.db"), session_lane=known_bad.LANE)
    known_bad.seed(fs)
    rows = known_bad.prove_blocked(fs)
    leaked = [r["key"] for r in rows if not r["blocked"]]
    assert not leaked, f"KNOWN-BAD artefacts that leaked through the gate: {leaked}"
    # the fake 17-study Xpert headline is DOUBLE-blocked: synthetic AND implausible
    fake = next(r for r in rows if r["key"] == "TB.Xpert.fake17.headline")
    assert not fake["plausibility_ok"]
    assert any("dispersion" in v for v in fake["plausibility_reasons"])


@pytest.mark.parametrize("key", [b.key for b in known_bad.KNOWN_BAD])
def test_each_known_bad_key_raises(tmp_path, key):
    fs = FactStore(str(tmp_path / "each.db"), session_lane=known_bad.LANE)
    known_bad.seed(fs)
    with pytest.raises(FactStoreError):
        fs.consume_verified(key)


# --- THE strongest trip: a fabricated number on the REAL demo key is rejected ---

def test_fabricated_number_on_a_real_slide_key_cannot_be_consumed(tmp_path):
    """If someone tried to put the fake 17-study Xpert Se onto the real slide's key,
    the store must refuse it. We seed the fabrication synthetic, then a lane that
    READS it (rehydrate-on-read taint) re-emits it on the real Xpert key — the
    laundering path — and consume must still FAIL LOUD."""
    db = str(tmp_path / "launder.db")
    # lane 1 seeds the fabrication synthetic
    fs1 = FactStore(db, session_lane="fabricator")
    fs1.record_synthetic("TB.Xpert.fake17.sensitivity", 0.858,
                         source="DTA70", lane="fabricator")
    fs1.close()
    # lane 2 reads the synthetic value (taints the lane) then re-emits it as a fresh
    # "real" root fact on the REAL slide key — no lineage edge (context-window launder)
    fs2 = FactStore(db, session_lane="slide-author")
    _ = fs2.facts_for("TB.Xpert.fake17.sensitivity")   # public read of synthetic -> taints "slide-author"
    # emit via the now-tainted session lane
    fid = fs2.record_real("TB.Xpert.real4.sensitivity", 0.858,
                          source="(claims real)", lane="slide-author")
    # forced synthetic by BOTH rehydrate-on-read taint and value-taint (0.858 copied)
    assert fs2.get(fid).is_synthetic
    with pytest.raises(SyntheticFactError):
        fs2.consume_verified("TB.Xpert.real4.sensitivity")
    fs2.close()


# --- Other lanes (2-6): every headline number survives the gate ----------------

def test_every_other_lane_number_passes_consume(tmp_path):
    from overmind.factstore.lanes import other_lanes
    fs = FactStore(str(tmp_path / "other.db"), session_lane="other-lanes")
    other_lanes.wire(fs)
    rows = other_lanes.report(fs)
    failed = [r["key"] for r in rows if not r["ok"]]
    assert not failed, f"other-lane numbers that failed consume_verified: {failed}"


def test_harms_completeness_headline_is_auto_gated(tmp_path):
    """The harms-completeness claim is a confirming headline; the lane declares it as
    an ordinary real fact, but the hypothesis registry auto-classifies it, so it needs
    cross-family review — one family must fail."""
    from overmind.factstore.lanes import other_lanes, hypotheses
    fs = FactStore(str(tmp_path / "hc.db"), session_lane="harms")
    hypotheses.register_all(fs)
    fid = fs.record_real("harms.completeness.headline",
                         {"registry_terms": 32, "review_pooled_terms": 1},
                         source="harms-asymmetry", lane="local_facbb6c1")
    assert fs.get(fid).confirms_hypothesis is True
    with pytest.raises(FactStoreError):
        fs.verify(fid, families=["openai"])


# --- Lane-work in-flight checkpointing (jobs resume; work is NOT redone) --------

def test_lane_work_resumes_without_recompute(tmp_path):
    """A lane's expensive per-number step, wrapped in get_or_compute, is not redone
    after a simulated restart — closes 'jobs resume but lane work is redone'."""
    db = str(tmp_path / "ckpt.db")
    calls = {"n": 0}

    def expensive():
        calls["n"] += 1
        return 2262

    fs1 = FactStore(db, session_lane="pico")
    v1 = fs1.get_or_compute("pico.expensive.count", expensive,
                            source="PICO-MAP:50", lane="local_b9ba3a2f")
    fs1.close()
    fs2 = FactStore(db, session_lane="pico")           # simulate restart
    v2 = fs2.get_or_compute("pico.expensive.count", expensive,
                            source="PICO-MAP:50", lane="local_b9ba3a2f")
    fs2.close()
    assert v1 == v2 == 2262
    assert calls["n"] == 1                             # computed once, resumed after


# --- The combined runner returns a clean verdict -------------------------------

def test_combined_runner_all_green(tmp_path):
    from overmind.factstore.lanes import __main__ as runner
    rc = runner.run(str(tmp_path / "combined.db"))
    assert rc == 0
