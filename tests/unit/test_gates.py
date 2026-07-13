"""Trip-tests for overmind.gates — the 2026-07-13 enforcement layer.

Discipline (Mahmood): every gate needs a trip-test that FAILS before the fix and
PASSES after. A gate that cannot be tripped is not real. Each test below shows
BOTH: (a) the pre-fix hole — the raw path that let the bad value through — as a
documented baseline, and (b) the gate closing it.
"""
import pytest

from overmind.factstore.store import FactStore
from overmind.gates import (
    Claim, ClaimType, SourceTier,
    ExportBlocked, guard_export, guard_export_from_store,
    LayerCoverageError, guard_layers,
    ErrorClass, BlindSpotError, coverage_report, assert_no_shared_blindspot,
    DEFAULT_CHECKS,
    Vote, PanelError, AbstentionError, adjudicate,
    LaneSpec, LaneRefused, admit_lane,
)
from overmind.gates.panel import Verdict


# ---------------------------------------------------------------------------
# GATE 1 — export boundary (F2). The fake DTA70 figure must be impossible.
# ---------------------------------------------------------------------------

def test_gate1_before_raw_store_read_leaks_synthetic():
    """PRE-FIX BASELINE: the raw store path returns the fabricated value with no
    guard. This is exactly how DTA70 reached the briefing — taint tracked, not
    enforced."""
    fs = FactStore(":memory:")
    fid = fs.record_synthetic("TB.DTA.xpert.sens", 85.8,
                              source="DTA70:synthetic", lane="dta70")
    # Nothing stops a naive exporter from reading .value straight out:
    assert fs.get(fid).value == 85.8          # the leak the boundary must close
    assert fs.get(fid).is_synthetic is True   # the store KNEW; nobody asked


def test_gate1_after_export_from_store_blocks_dta70():
    """POST-FIX: routing the same fact through the export boundary fails closed."""
    fs = FactStore(":memory:")
    fs.record_synthetic("TB.DTA.xpert.sens", 85.8,
                        source="DTA70:synthetic", lane="dta70")
    with pytest.raises(Exception) as ei:   # SyntheticFactError (a FactStoreError)
        guard_export_from_store("TB.DTA.xpert.sens", fs)
    assert "synthetic" in str(ei.value).lower()


def test_gate1_typed_claim_blocks_synthetic_and_unlocated():
    syn = Claim("Xpert sensitivity", 85.8, SourceTier.SYNTHETIC, "DTA70")
    with pytest.raises(ExportBlocked):
        guard_export(syn)

    unlocated = Claim("malaria RR", 0.48, SourceTier.ABSTRACT, locator="")
    with pytest.raises(ExportBlocked):
        guard_export(unlocated)

    tainted = Claim("pooled TB effect", 0.7, SourceTier.DERIVED, "calc#1",
                    derived_from=(Claim("x", 1, SourceTier.SYNTHETIC, "DTA70"),))
    with pytest.raises(ExportBlocked):
        guard_export(tainted)


def test_gate1_real_located_claim_passes():
    ok = Claim("malaria RR", 0.48, SourceTier.ABSTRACT, "PMID:31234567#abstract")
    assert guard_export(ok) is ok


def test_gate1_export_rejects_bare_number():
    with pytest.raises(ExportBlocked):
        guard_export(0.48)  # a raw float can never reach the boundary


# ---------------------------------------------------------------------------
# GATE 2 — three-layer coverage gate (F1). Registry-only ceiling must refuse.
# ---------------------------------------------------------------------------

def test_gate2_before_registry_only_recall_would_ship():
    """PRE-FIX BASELINE: as a bare Claim with no layer discipline, a registry-only
    recall number is just a value — nothing asks 'did you try the abstract?'."""
    c = Claim("reconstruction recall", 0.14, SourceTier.REGISTRY, "aact",
              claim_type=ClaimType.RECALL, layers_queried=(SourceTier.REGISTRY,))
    assert c.value == 0.14  # it would have been reported verbatim (the F1 error)


def test_gate2_after_registry_only_recall_blocked():
    """POST-FIX: the layer gate refuses a recall that never queried the abstract."""
    c = Claim("reconstruction recall", 0.14, SourceTier.REGISTRY, "aact",
              claim_type=ClaimType.RECALL, layers_queried=(SourceTier.REGISTRY,))
    with pytest.raises(LayerCoverageError) as ei:
        guard_layers(c)
    assert "abstract" in str(ei.value).lower()


def test_gate2_cell_exact_accuracy_needs_the_source_that_has_the_cell():
    """The '17% cell-exact' case: accuracy claimed without OA full text refuses."""
    c = Claim("cell-exact reconstruction", 0.17, SourceTier.REGISTRY, "aact",
              claim_type=ClaimType.ACCURACY, layers_queried=(SourceTier.REGISTRY,))
    with pytest.raises(LayerCoverageError):
        guard_layers(c)


def test_gate2_all_layers_queried_passes():
    c = Claim("reconstruction recall", 0.80, SourceTier.OA_FULLTEXT, "corpus#1",
              claim_type=ClaimType.RECALL,
              layers_queried=(SourceTier.ABSTRACT, SourceTier.OA_FULLTEXT))
    assert guard_layers(c) is c


def test_gate2_point_claim_is_passthrough():
    c = Claim("one trial's RR", 0.48, SourceTier.ABSTRACT, "PMID:1#abs",
              claim_type=ClaimType.POINT)
    assert guard_layers(c) is c


# ---------------------------------------------------------------------------
# GATE 3 — blind-spot map (F3). Three checks blind to selection must be LOUD.
# ---------------------------------------------------------------------------

def test_gate3_before_three_agreeing_checks_share_a_blindspot():
    """PRE-FIX BASELINE: arithmetic + transparency + same-family panel all pass a
    selection error, and their agreement reads as safety."""
    trio = [DEFAULT_CHECKS["arithmetic"], DEFAULT_CHECKS["transparency"],
            DEFAULT_CHECKS["same_family_panel"]]
    report = coverage_report(trio)
    # every one of them says 'number OK' but NONE can see selection:
    assert report[ErrorClass.SELECTION] == []
    assert report[ErrorClass.SYCOPHANCY] == []


def test_gate3_after_shared_blindspot_is_loud_failure():
    """POST-FIX: the same trio trips a BlindSpotError instead of passing quietly."""
    trio = [DEFAULT_CHECKS["arithmetic"], DEFAULT_CHECKS["transparency"],
            DEFAULT_CHECKS["same_family_panel"]]
    with pytest.raises(BlindSpotError) as ei:
        assert_no_shared_blindspot(trio)
    assert "selection" in str(ei.value).lower()


def test_gate3_full_check_set_covers_every_error_class():
    checks = [DEFAULT_CHECKS[n] for n in
              ("arithmetic", "layer_gate", "export_gate", "cross_family_panel")]
    report = assert_no_shared_blindspot(checks)   # must not raise
    for ec in ErrorClass:
        assert report[ec], f"no check sees {ec.value}"


def test_gate3_check_must_declare_where_it_is_blind():
    from overmind.gates.blindspot_map import Check
    with pytest.raises(ValueError):
        Check("liar", sees=frozenset({ErrorClass.SELECTION}),
              blind_to=frozenset())  # does not account for the other classes


# ---------------------------------------------------------------------------
# GATE 4 — cross-family panel (F4/F6/F7). Fail-closed; abstention != vote.
# ---------------------------------------------------------------------------

def test_gate4_before_empty_vendor_would_count():
    """PRE-FIX BASELINE: a naive tally counts a dead vendor's empty reply as if it
    agreed (agy returned empty and exited 0)."""
    votes = [Vote("anthropic", Verdict.CONFIRM),
             Vote("google", Verdict.CONFIRM, empty=True)]  # dead vendor
    naive_yes = sum(1 for v in votes if v.verdict is Verdict.CONFIRM)
    assert naive_yes == 2          # the fail-open: silence counted as a yes


def test_gate4_after_empty_vote_never_counts():
    """POST-FIX: the empty vote is dropped; a flattering claim then lacks its 2nd
    family and is blocked."""
    claim = Claim("our harness caught 5 errors", 5, SourceTier.ABSTRACT,
                  "self", flatters_user=True, confirms_hypothesis=True)
    votes = [Vote("anthropic", Verdict.CONFIRM),
             Vote("google", Verdict.CONFIRM, empty=True)]
    with pytest.raises(PanelError):
        adjudicate(claim, votes)


def test_gate4_flattering_claim_needs_two_families():
    claim = Claim("result Mahmood wanted", 4.0, SourceTier.ABSTRACT, "x",
                  flatters_user=True)
    one_family = [Vote("anthropic", Verdict.CONFIRM),
                  Vote("anthropic", Verdict.CONFIRM)]  # same family twice
    with pytest.raises(PanelError):
        adjudicate(claim, one_family)
    two_families = [Vote("anthropic", Verdict.CONFIRM),
                    Vote("openai", Verdict.CONFIRM)]
    assert adjudicate(claim, two_families)["passed"]


def test_gate4_novelty_needs_other_family_prior_art_pass():
    claim = Claim("novel abstain gate", None, SourceTier.ABSTRACT, "x",
                  claim_type=ClaimType.NOVELTY)
    # only same-family "looks novel" -> blocked (this is the Dawid-Skene case)
    with pytest.raises(PanelError):
        adjudicate(claim, [Vote("anthropic", Verdict.CONFIRM)],
                   claimant_family="anthropic")
    # a different family confirms no prior art -> passes
    assert adjudicate(claim, [Vote("openai", Verdict.CONFIRM)],
                      claimant_family="anthropic")["passed"]


def test_gate4_all_abstain_cannot_pass():
    claim = Claim("flattering", 1, SourceTier.ABSTRACT, "x", flatters_user=True)
    with pytest.raises(AbstentionError):
        adjudicate(claim, [Vote("openai", Verdict.ABSTAIN),
                           Vote("google", Verdict.CONFIRM, empty=True)])


# ---------------------------------------------------------------------------
# GATE 5 — elaboration brake (F5). A lane serving nothing must be refused.
# ---------------------------------------------------------------------------

def test_gate5_before_ornament_lane_has_no_cost():
    """PRE-FIX BASELINE: a LaneSpec can be constructed for pure ornament — nothing
    charges for starting it (the ~30-lane sprawl)."""
    orn = LaneSpec("hadith-grading", serves="explore", beneficiary="the field",
                   deliverable="", evidence_source="", stop_condition="")
    assert orn.name == "hadith-grading"   # it exists, uncharged


def test_gate5_after_ornament_lane_refused():
    orn = LaneSpec("hadith-grading", serves="explore", beneficiary="the field",
                   deliverable="", evidence_source="", stop_condition="")
    with pytest.raises(LaneRefused) as ei:
        admit_lane(orn)
    assert "kampala" in str(ei.value).lower() or "ornament" in str(ei.value).lower()


def test_gate5_real_lane_admitted():
    lane = LaneSpec(
        "export-boundary-gate", serves="F2",
        beneficiary="Makerere reviewer receiving a briefing",
        deliverable="fail-closed export gate + trip tests",
        evidence_source="F:/overmind/overmind/factstore",
        stop_condition="DTA70 export raises + tests green")
    assert admit_lane(lane, active=0) is lane


def test_gate5_concurrency_cap_enforced():
    lane = LaneSpec("x", serves="F1", beneficiary="researcher",
                    deliverable="d", evidence_source="e", stop_condition="s")
    with pytest.raises(LaneRefused):
        admit_lane(lane, active=3)


def test_gate5_kampala_datum_justifies_a_non_failure_lane():
    lane = LaneSpec(
        "malaria-oa-recall", serves="coverage-measurement",
        beneficiary="Makerere malaria reviewer",
        deliverable="OA recall number for malaria RCTs",
        evidence_source="EuropePMC + AACT",
        stop_condition="recall reported with layers declared",
        kampala_datum="malaria RCT OA availability = 70.3%")
    assert admit_lane(lane) is lane


# ===========================================================================
# ROUND 2 — fixes for holes found by the cross-vendor gate review (2026-07-13).
# Codex (openai) reviewed the source; agy (google) tried to bypass. Each hole
# below FAILED before the round-2 fix and PASSES after.
# ===========================================================================

def test_gate4_refutation_is_fail_closed_codex_bug():
    """Codex found: a flattering claim passed on any(CONFIRM) even when another
    family REFUTED. A confirm must NOT override cross-family dissent."""
    claim = Claim("result Mahmood wanted", 4.0, SourceTier.ABSTRACT, "x",
                  flatters_user=True)
    split = [Vote("openai", Verdict.CONFIRM), Vote("google", Verdict.REFUTE)]
    with pytest.raises(PanelError) as ei:
        adjudicate(claim, split)
    assert "refut" in str(ei.value).lower()


def test_gate4_novelty_prior_art_found_blocks_even_with_a_confirm():
    claim = Claim("novel gate", None, SourceTier.ABSTRACT, "x",
                  claim_type=ClaimType.NOVELTY)
    votes = [Vote("openai", Verdict.CONFIRM), Vote("google", Verdict.REFUTE)]
    with pytest.raises(PanelError):
        adjudicate(claim, votes, claimant_family="anthropic")


def test_gate1_fake_locator_is_rejected():
    """agy/Codex bypass: a plausible-but-fabricated locator string."""
    spoof = Claim("Xpert sensitivity", 85.8, SourceTier.ABSTRACT,
                  "PMID:fake#abstract")
    with pytest.raises(ExportBlocked) as ei:
        guard_export(spoof)
    assert "placeholder" in str(ei.value).lower() or "locator" in str(ei.value).lower()

    no_anchor = Claim("malaria RR", 0.48, SourceTier.ABSTRACT, "PMID:31234567")
    with pytest.raises(ExportBlocked):
        guard_export(no_anchor)  # id but no field/line anchor

    no_id = Claim("malaria RR", 0.48, SourceTier.ABSTRACT, "FakeLocator-123")
    with pytest.raises(ExportBlocked):
        guard_export(no_id)


def test_gate1_real_shaped_locator_passes():
    ok = Claim("malaria RR", 0.48, SourceTier.ABSTRACT, "PMID:31234567#abstract")
    assert guard_export(ok) is ok
    nct = Claim("arm N", 250, SourceTier.REGISTRY, "NCT01439880#designGroups[0]")
    assert guard_export(nct) is nct


def test_gate2_aggregate_language_mislabeled_as_point_is_blocked():
    """Codex: mislabel an aggregate as POINT to skip the layer gate."""
    sneaky = Claim("cell-exact recall across all trials", 0.17,
                   SourceTier.REGISTRY, "aact", claim_type=ClaimType.POINT)
    with pytest.raises(LayerCoverageError) as ei:
        guard_layers(sneaky)
    assert "mislabel" in str(ei.value).lower() or "aggregate" in str(ei.value).lower()


def test_gate3_proven_only_rejects_declared_but_unproven_sight():
    """Both reviewers: a check can just declare sees=ALL. Under proven_only, a
    class only counts if the check has a capability fixture for it."""
    from overmind.gates.blindspot_map import Check
    liar = Check("liar", sees=frozenset(ErrorClass),
                 blind_to=frozenset(), proven=frozenset())  # claims all, proves none
    # declaration-only coverage is 'full' and passes the weak form:
    assert_no_shared_blindspot([liar])                       # weak: no raise
    # but the strong (proven) form sees straight through it:
    with pytest.raises(BlindSpotError):
        assert_no_shared_blindspot([liar], proven_only=True)


def test_gate3_real_gates_have_demonstrated_trip_power():
    """Ties each gate's DECLARED sight to a REAL trip through the actual gate
    function — the capability probe Codex asked for. If any of these stops
    raising, the corresponding `proven=` claim is a lie and must be removed."""
    # export_gate PROVEN on FABRICATION:
    with pytest.raises(ExportBlocked):
        guard_export(Claim("x", 1, SourceTier.SYNTHETIC, "DTA70"))
    # layer_gate PROVEN on SELECTION / REACH_VS_ACCURACY:
    with pytest.raises(LayerCoverageError):
        guard_layers(Claim("recall", 0.14, SourceTier.REGISTRY, "aact",
                           claim_type=ClaimType.RECALL,
                           layers_queried=(SourceTier.REGISTRY,)))
    # cross_family_panel PROVEN on SYCOPHANCY and PRIOR_ART:
    with pytest.raises(PanelError):
        adjudicate(Claim("flatter", 1, SourceTier.ABSTRACT, "x", flatters_user=True),
                   [Vote("openai", Verdict.CONFIRM), Vote("google", Verdict.REFUTE)])
    with pytest.raises(PanelError):
        adjudicate(Claim("novel", None, SourceTier.ABSTRACT, "x",
                         claim_type=ClaimType.NOVELTY),
                   [Vote("google", Verdict.REFUTE)], claimant_family="anthropic")
