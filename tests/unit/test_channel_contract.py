"""Part III trip-tests — the binding evidence contract.

Every test documents a pre-fix hole and its post-fix block. The organising
claim of Part III is: *a bare number has no type-legal path to output.* These
tests are the proof, in the fail-before / pass-after form the earlier gates use.
"""
from __future__ import annotations

import pytest

from overmind.gates.contract import Claim, ClaimType, SourceTier
from overmind.gates.channel import ExportChannel, ChannelViolation, emit
from overmind.gates.resolver import LocatorResolver, Resolution
from overmind.gates.priorart import (
    PriorArtSearch, Candidate, guard_novelty, PriorArtError,
    execute_prior_art_search,
)
from overmind.gates import enforcement


# A stub resolver so channel tests do not depend on the AACT snapshot being
# present. It says "resolved" for NCT12345678 with value 3, refuses everything
# else — small, deterministic, and it lets us prove the channel USES resolution.
class _StubResolver(LocatorResolver):
    def __init__(self):
        super().__init__(aact_path=None)

    def resolve(self, locator, claimed_value=None):
        if "NCT12345678" in (locator or ""):
            ok = claimed_value in (None, 3)
            return Resolution(True, ok if claimed_value is not None else None,
                              "stub", ground_truth=3,
                              reason="" if ok else "value mismatch")
        return Resolution(False, None, "stub", reason="unknown id")


def _chan():
    return ExportChannel(resolver=_StubResolver())


# --- THE CENTRAL CLAIM: a bare number cannot reach output --------------------

@pytest.mark.parametrize("bare", [42, 3.14, "85.8%", 0.67, [1, 2]])
def test_channel_refuses_bare_number(bare):
    """The type sink. A float/int/str/list has no path — the channel refuses it
    before anything renders. This is the illegal state made unrepresentable."""
    with pytest.raises(ChannelViolation, match="only validated Claim"):
        _chan().emit(bare)


def test_there_is_no_emit_raw_backdoor():
    """No public function on the channel accepts a raw value. If someone adds one,
    this test should force them to justify it here."""
    ch = _chan()
    public_callables = [n for n in dir(ch) if not n.startswith("_") and callable(getattr(ch, n))]
    # only emit / emit_all are sanctioned entry points
    assert set(public_callables) <= {"emit", "emit_all"}, (
        f"unexpected public entry points on the channel: {public_callables} — "
        f"a new sink is a new bypass; it must run the gates.")


# --- resolution: the gated-laundering residual ------------------------------

def test_channel_blocks_real_shaped_but_unresolvable_locator():
    """Fail-before: export_gate accepts a real-SHAPED locator. Fail-after: the
    channel follows it and refuses when it does not resolve (laundering closed)."""
    launder = Claim("fabricated but plausible", 99.9, SourceTier.REGISTRY,
                    "NCT00000001#om[7]")
    with pytest.raises(ChannelViolation, match="did not resolve"):
        _chan().emit(launder)


def test_channel_passes_resolvable_value_matched_claim():
    """A number whose locator resolves AND whose value matches ground truth passes."""
    good = Claim("matched arm count", 3, SourceTier.REGISTRY, "NCT12345678#armcount=3")
    rendered = _chan().emit(good)
    assert rendered.value == 3
    assert "resolve:stub" in rendered.passed_gates


def test_channel_blocks_resolvable_but_value_mismatch():
    """Resolves to a real record, but the claimed value != ground truth (identity
    gate). Blocked."""
    wrong = Claim("wrong arm count", 5, SourceTier.REGISTRY, "NCT12345678#armcount=5")
    with pytest.raises(ChannelViolation, match="did not resolve|mismatch"):
        _chan().emit(wrong)


def test_channel_still_blocks_synthetic_before_resolution():
    syn = Claim("DTA70 fake", 85.8, SourceTier.SYNTHETIC, "NCT12345678#om[1]", synthetic=True)
    with pytest.raises(ChannelViolation, match="synthetic"):
        _chan().emit(syn)


def test_derived_claim_requires_lineage():
    """A DERIVED claim skips locator resolution (it inherits parents') — so it must
    actually NAME parents, else taint/provenance is silently dropped."""
    orphan = Claim("derived with no parents", 1.0, SourceTier.DERIVED, "computed")
    with pytest.raises(ChannelViolation, match="no parents|lineage"):
        _chan().emit(orphan)
    parent = Claim("p", 3, SourceTier.REGISTRY, "NCT12345678#armcount=3")
    child = Claim("ratio", 1.5, SourceTier.DERIVED, "computed", derived_from=(parent,))
    assert _chan().emit(child).value == 1.5


# --- panel binding: flattering / novelty claims -----------------------------

def test_channel_blocks_flattering_claim_without_panel_verdict():
    # value 3 matches the stub ground truth, so it clears resolution and reaches
    # the panel check — which must block it for lacking a cleared verdict.
    flat = Claim("our method is best", 3, SourceTier.REGISTRY,
                 "NCT12345678#armcount=3", flatters_user=True)
    with pytest.raises(ChannelViolation, match="panel"):
        _chan().emit(flat)


def test_channel_passes_flattering_claim_with_cleared_panel():
    flat = Claim("our method scored well", 3, SourceTier.REGISTRY,
                 "NCT12345678#armcount=3", flatters_user=True,
                 meta={"panel_verdict": "passed"})
    assert _chan().emit(flat).value == 3


# --- F7: executed prior-art, not a checkbox ---------------------------------

def test_novelty_without_search_is_blocked():
    c = Claim("novel method X", 1, SourceTier.REGISTRY, "NCT12345678#armcount=3",
              claim_type=ClaimType.NOVELTY)
    with pytest.raises(PriorArtError, match="no PriorArtSearch"):
        guard_novelty(c, None)


def test_novelty_with_unexecuted_search_is_blocked():
    """A hand-built empty search (executed=False) is a checkbox — refused."""
    fake = PriorArtSearch(subject="novel method X", queries=("x",), sources=("pubmed",),
                          reviewer_family="openai", executed=False)
    with pytest.raises(PriorArtError, match="never executed"):
        guard_novelty(Claim("novel method X", 1, SourceTier.REGISTRY,
                            "NCT12345678#armcount=3", claim_type=ClaimType.NOVELTY), fake)


def test_novelty_same_family_search_is_blocked():
    # a validly-signed but SAME-family search must still be refused (F7 decorrelation)
    same = execute_prior_art_search(
        "X", ["q"],
        executor=lambda s, q: ([Candidate("adjacent", similar=False)], "self", "anthropic"))
    with pytest.raises(PriorArtError, match="same family"):
        guard_novelty(Claim("X", 1, SourceTier.REGISTRY, "NCT1#a",
                            claim_type=ClaimType.NOVELTY), same, claimant_family="anthropic")


def test_novelty_with_prior_art_found_is_blocked():
    found = execute_prior_art_search(
        "X", ["q"],
        executor=lambda s, q: ([Candidate("Dawid & Skene 1979", similar=True,
                                           reason="same EM label model")], "pubmed", "openai"))
    with pytest.raises(PriorArtError, match="prior art found"):
        guard_novelty(Claim("X", 1, SourceTier.REGISTRY, "NCT1#a",
                            claim_type=ClaimType.NOVELTY), found)


def test_novelty_passes_with_clean_different_family_search():
    clean = execute_prior_art_search(
        "X", ["q1", "q2"], sources=["pubmed", "codex"],
        executor=lambda s, q: ([Candidate("adjacent work", similar=False,
                                           reason="different problem")], "pubmed", "openai"))
    out = guard_novelty(Claim("X", 1, SourceTier.REGISTRY, "NCT1#a",
                             claim_type=ClaimType.NOVELTY), clean)
    assert out.executed and out.token_valid


def test_execute_prior_art_sets_executed_via_stub_executor():
    """execute_prior_art_search is the ONLY thing that sets executed=True — prove
    it does, with a stub standing in for the codex backend."""
    def stub(subject, queries):
        return [Candidate("unrelated 2001", similar=False)], "stub-corpus", "openai"
    s = execute_prior_art_search("my method", ["q"], executor=stub)
    assert s.executed and s.reviewer_family == "openai" and s.sources == ("stub-corpus",)


# --- round 2: both families said 'executed=True' is forgeable. Now it is signed --

def test_forged_executed_flag_is_blocked_without_valid_token():
    """agy/Codex round-2: a hand-built PriorArtSearch(executed=True) with no valid
    HMAC token cannot clear the gate."""
    forged = PriorArtSearch(subject="X", queries=("q",), sources=("pubmed",),
                            reviewer_family="openai", executed=True, token="")
    with pytest.raises(PriorArtError, match="no valid signature"):
        guard_novelty(Claim("X", 1, SourceTier.REGISTRY, "NCT1#a",
                            claim_type=ClaimType.NOVELTY), forged)


def test_mutated_search_invalidates_token():
    """Mutating any field after signing breaks the token (the whole point)."""
    def stub(subject, queries):
        return [Candidate("adjacent", similar=False)], "codex", "openai"
    s = execute_prior_art_search("real method", ["q"], executor=stub)
    assert s.token_valid
    # forge a 'clean' search that borrows the token but changes the candidates
    tampered = PriorArtSearch(subject=s.subject, queries=s.queries, sources=s.sources,
                              reviewer_family=s.reviewer_family,
                              candidates=(Candidate("suppressed prior art", similar=False),),
                              executed=True, token=s.token)
    assert not tampered.token_valid
    with pytest.raises(PriorArtError, match="no valid signature"):
        guard_novelty(Claim("real method", 1, SourceTier.REGISTRY, "NCT1#a",
                            claim_type=ClaimType.NOVELTY), tampered)


def test_signed_search_clears_the_gate():
    def stub(subject, queries):
        return [Candidate("adjacent", similar=False)], "codex", "openai"
    s = execute_prior_art_search("real method", ["q1", "q2"], executor=stub)
    out = guard_novelty(Claim("real method", 1, SourceTier.REGISTRY, "NCT1#a",
                             claim_type=ClaimType.NOVELTY), s)
    assert out.token_valid


# --- round 2: existence-only laundering (a real NCT, no value anchor) -----------

def test_existence_only_locator_blocks_a_value_bearing_claim():
    """agy round-2 #1 hole: a fabricated value must NOT ride in on a real-but-
    unanchored NCT. Uses the real AACT resolver (skips if snapshot absent)."""
    from overmind.gates.resolver import default_resolver
    r = default_resolver()
    probe = r.resolve("NCT04336189")  # exists; existence-only, no value
    if not probe.resolved:
        pytest.skip("AACT snapshot not present in this environment")
    # same real NCT, no value-pinning anchor, but a value IS claimed -> must fail
    res = r.resolve("NCT04336189#somenote", claimed_value=99.9)
    assert res.resolved is True and res.value_ok is False and not res.passes


def test_prior_art_replay_across_subjects_is_blocked():
    """Round-3 (Codex+agy): a valid signed search for subject A must NOT clear a
    novelty claim about subject B."""
    s_for_a = execute_prior_art_search(
        "method A", ["q"],
        executor=lambda a, b: ([Candidate("adjacent", similar=False)], "codex", "openai"))
    assert s_for_a.token_valid
    claim_b = Claim("method B", 1, SourceTier.REGISTRY, "NCT1#a", claim_type=ClaimType.NOVELTY)
    with pytest.raises(PriorArtError, match="different subject|replay"):
        guard_novelty(claim_b, s_for_a)


def test_derived_claim_with_fabricated_parent_is_blocked():
    """Round-3 (Codex confirmed a live `999` exploit): a DERIVED claim whose parent
    does not itself resolve must be refused — recursion to the leaves."""
    bad_parent = Claim("fabricated parent", 999, SourceTier.REGISTRY, "NCT00000009#armcount=9")
    child = Claim("derived fabrication", 999, SourceTier.DERIVED, "computed",
                  derived_from=(bad_parent,))
    with pytest.raises(ChannelViolation, match="un-exportable parent|did not resolve"):
        _chan().emit(child)


def test_derived_claim_with_good_parent_passes():
    good_parent = Claim("real arm count", 3, SourceTier.REGISTRY, "NCT12345678#armcount=3")
    child = Claim("derived ratio", 1.5, SourceTier.DERIVED, "computed",
                  derived_from=(good_parent,))
    assert _chan().emit(child).value == 1.5


def test_semantic_anchor_hijack_requires_declared_outcome():
    """Round-3 (both families): an #om[id] value claim must declare the outcome it
    expects (meta['outcome']); without it, a numeric coincidence would launder."""
    class _OmResolver(LocatorResolver):
        def __init__(self):
            super().__init__(aact_path=None)
        def resolve(self, locator, claimed_value=None):
            if "om[" in (locator or ""):
                return Resolution(True, True, "stub",
                                  ground_truth={"value": 60, "title": "Median age (years)"})
            return Resolution(False, None, "stub", reason="no")
    ch = ExportChannel(resolver=_OmResolver())
    # value 60 matches, but no declared outcome -> refused
    hijack = Claim("efficacy 60%", 60, SourceTier.REGISTRY, "NCT12345678#om[5]")
    with pytest.raises(ChannelViolation, match="expected outcome|anchor-hijack"):
        ch.emit(hijack)
    # declares the WRONG outcome (age) which happens to match AACT title -> here the
    # title IS median age, so a claim expecting 'efficacy' is refused
    wrong = Claim("efficacy 60%", 60, SourceTier.REGISTRY, "NCT12345678#om[5]",
                  meta={"outcome": "overall survival"})
    with pytest.raises(ChannelViolation, match="anchor-hijack|does not"):
        ch.emit(wrong)
    # declares the matching outcome -> passes
    ok = Claim("median age", 60, SourceTier.REGISTRY, "NCT12345678#om[5]",
               meta={"outcome": "Median age"})
    assert ch.emit(ok).value == 60


def test_lying_claim_text_with_matching_meta_is_blocked():
    """Codex round-3 break: a claim whose meta['outcome'] matches AACT but whose
    TEXT lies ('efficacy 60%' anchored to median-age 60) must be refused — the
    stated meaning must agree with the true meaning, not just the declared one."""
    class _OmResolver(LocatorResolver):
        def __init__(self):
            super().__init__(aact_path=None)
        def resolve(self, locator, claimed_value=None):
            return Resolution(True, True, "stub",
                              ground_truth={"value": 60, "title": "Median age (years)"})
    ch = ExportChannel(resolver=_OmResolver())
    liar = Claim("efficacy 60%", 60, SourceTier.REGISTRY, "NCT12345678#om[5]",
                 meta={"outcome": "Median age"})  # meta matches AACT, text lies
    with pytest.raises(ChannelViolation, match="lying|does not|anchor-hijack"):
        ch.emit(liar)


def test_derived_parent_must_clear_layer_gate_too():
    """Codex round-3 break: a parent that would fail the layer gate (registry-only
    recall) must not launder through a derived child."""
    # a RECALL parent that only queried the registry would be blocked directly...
    bad_parent = Claim("registry-only recall", 0.14, SourceTier.REGISTRY,
                       "NCT12345678#armcount=3", claim_type=ClaimType.RECALL,
                       layers_queried=(SourceTier.REGISTRY,))
    child = Claim("derived from a bad-recall parent", 0.28, SourceTier.DERIVED,
                  "computed", derived_from=(bad_parent,))
    with pytest.raises(ChannelViolation, match="did NOT query|un-exportable parent|F1"):
        _chan().emit(child)


# --- round 4: arm / timepoint / unit binding (the SELECTION error) --------------

class _DimResolver(LocatorResolver):
    """A stub whose om ground truth carries arm/timepoint/unit — so the binding can
    be proven deterministically without the AACT snapshot."""
    def __init__(self, **gt):
        super().__init__(aact_path=None)
        self._gt = {"value": 11.1, "title": "Number of Oocytes Retrieved",
                    "arm": "GnRH Agonist (GONAPEPTYL)", "timepoint": "day of oocyte retrieval",
                    "unit": "Oocytes"}
        self._gt.update(gt)
    def resolve(self, locator, claimed_value=None):
        if "om[" in (locator or ""):
            return Resolution(True, True, "stub", ground_truth=dict(self._gt))
        return Resolution(False, None, "stub", reason="no")


def _dim_claim(**meta):
    base = {"outcome": "Number of Oocytes Retrieved", "arm": "GnRH Agonist (GONAPEPTYL)",
            "timepoint": "day of oocyte retrieval", "unit": "Oocytes"}
    base.update(meta)
    return Claim("oocytes retrieved", 11.1, SourceTier.REGISTRY,
                 "NCT03809429#om[1571418270]", meta=base)


def test_om_claim_with_full_arm_timepoint_unit_passes():
    ch = ExportChannel(resolver=_DimResolver())
    assert ch.emit(_dim_claim()).value == 11.1


def test_om_claim_missing_arm_is_blocked():
    """The number is real for THIS trial+outcome but the claim never says which arm —
    exactly how 11.1 (agonist) gets shipped as if it were 9.6 (antagonist)."""
    ch = ExportChannel(resolver=_DimResolver())
    with pytest.raises(ChannelViolation, match="does not declare its arm|wrong arm"):
        ch.emit(_dim_claim(arm=""))


def test_om_claim_wrong_arm_is_blocked():
    ch = ExportChannel(resolver=_DimResolver())
    with pytest.raises(ChannelViolation, match="wrong arm|arm="):
        ch.emit(_dim_claim(arm="GnRH Antagonist (CETROTIDE)"))


def test_om_claim_wrong_timepoint_is_blocked():
    ch = ExportChannel(resolver=_DimResolver())
    with pytest.raises(ChannelViolation, match="timepoint"):
        ch.emit(_dim_claim(timepoint="week 52 follow-up"))


def test_om_claim_missing_unit_is_blocked():
    ch = ExportChannel(resolver=_DimResolver())
    with pytest.raises(ChannelViolation, match="unit"):
        ch.emit(_dim_claim(unit=""))


def test_dimension_binding_is_noop_when_ground_truth_lacks_it():
    """Backward compat: a resolver that does not surface arm/timepoint/unit (older
    stub, or an om with null fields) imposes no requirement — the binding is
    'required WHEN checkable', not 'always required'."""
    ch = ExportChannel(resolver=_DimResolver(arm=None, timepoint=None, unit=None))
    lean = Claim("oocytes retrieved", 11.1, SourceTier.REGISTRY,
                 "NCT03809429#om[1]", meta={"outcome": "Number of Oocytes Retrieved"})
    assert ch.emit(lean).value == 11.1


def test_real_aact_wrong_arm_selection_error_blocks():
    """End-to-end on the AACT snapshot (skips if absent): NCT03809429 om 1571418270
    is 11.1 oocytes for the AGONIST arm. A claim that declares the ANTAGONIST arm for
    that same number is the wrong-arm selection error and must block."""
    from overmind.gates.resolver import default_resolver
    r = default_resolver()
    probe = r.resolve("NCT03809429#om[1571418270]", claimed_value=11.1)
    if not probe.resolved:
        pytest.skip("AACT snapshot not present")
    assert isinstance(probe.ground_truth, dict) and probe.ground_truth.get("arm")
    ch = ExportChannel(resolver=r)
    right = Claim("oocytes retrieved", 11.1, SourceTier.REGISTRY,
                  "NCT03809429#om[1571418270]",
                  meta={"outcome": "Number of Oocytes Retrieved",
                        "arm": probe.ground_truth["arm"],
                        "timepoint": probe.ground_truth.get("timepoint") or "n/a",
                        "unit": probe.ground_truth.get("unit") or "n/a"})
    assert ch.emit(right).value == 11.1
    wrong = Claim("oocytes retrieved", 11.1, SourceTier.REGISTRY,
                  "NCT03809429#om[1571418270]",
                  meta={"outcome": "Number of Oocytes Retrieved",
                        "arm": "GnRH Antagonist (CETROTIDE)",
                        "timepoint": probe.ground_truth.get("timepoint") or "n/a",
                        "unit": probe.ground_truth.get("unit") or "n/a"})
    with pytest.raises(ChannelViolation, match="wrong arm|arm="):
        ch.emit(wrong)


# --- round 4: the smaller residuals, named and probed --------------------------

def test_durable_key_flag_reflects_env(monkeypatch):
    """Residual #1: a token is portable across processes ONLY with the env key."""
    from overmind.gates import priorart
    monkeypatch.delenv("OVERMIND_PRIORART_KEY", raising=False)
    assert priorart.has_durable_key() is False
    monkeypatch.setenv("OVERMIND_PRIORART_KEY", "shared-secret")
    assert priorart.has_durable_key() is True


def test_search_records_executor_provenance():
    """Residual #2: the search records WHICH executor ran and whether it was the
    sanctioned cross-process default — so an injected in-process stub is visible,
    not indistinguishable from a real decorrelated search."""
    s = execute_prior_art_search(
        "X", ["q"],
        executor=lambda a, b: ([Candidate("adjacent", similar=False)], "codex", "openai"))
    assert s.meta["sanctioned_executor"] is False   # a stub, not _codex_executor
    assert "executor" in s.meta and "durable_key" in s.meta


def test_token_portable_only_with_shared_key(monkeypatch):
    """The concrete cross-process failure: mint under key A, verify under key B ->
    invalid. Set a shared key and the same token verifies. This is why has_durable_key
    matters — the per-process fallback is fail-closed across a boundary."""
    from overmind.gates import priorart
    monkeypatch.setenv("OVERMIND_PRIORART_KEY", "process-A-key")
    s = execute_prior_art_search(
        "X", ["q"], executor=lambda a, b: ([Candidate("adj", similar=False)], "codex", "openai"))
    assert s.token_valid                              # verifies under the same key
    monkeypatch.setenv("OVERMIND_PRIORART_KEY", "process-B-key")
    assert s.token_valid is False                     # a different process key -> fails closed


# --- round 4 re-attack: Codex's dose false-accept + sanctioned executor ----------

def test_dose_arm_false_accept_is_now_blocked():
    """Codex round-4: 'IGIV-C 0.2 g/kg' and 'IGIV-C 0.4 g/kg' both tokenised to
    {igiv, infusion} and a wrong-DOSE arm passed. The dose numbers now discriminate."""
    ch = ExportChannel(resolver=_DimResolver(
        arm="IGIV-C 0.2 g/kg bw/Infusion (2 mL/kg bw)"))
    right = Claim("oocytes retrieved", 11.1, SourceTier.REGISTRY,
                  "NCT03809429#om[1]",
                  meta={"outcome": "Number of Oocytes Retrieved",
                        "arm": "IGIV-C 0.2 g/kg bw/Infusion (2 mL/kg bw)",
                        "timepoint": "day of oocyte retrieval", "unit": "Oocytes"})
    assert ch.emit(right).value == 11.1
    wrong = Claim("oocytes retrieved", 11.1, SourceTier.REGISTRY,
                  "NCT03809429#om[1]",
                  meta={"outcome": "Number of Oocytes Retrieved",
                        "arm": "IGIV-C 0.4 g/kg bw/Infusion (4 mL/kg bw)",
                        "timepoint": "day of oocyte retrieval", "unit": "Oocytes"})
    with pytest.raises(ChannelViolation, match="wrong arm|arm="):
        ch.emit(wrong)


def test_vague_arm_without_dose_is_blocked():
    """Codex round-4: 'Duloxetine' must NOT match a specific-dose arm — a vague label
    that fits both 60 mg and 120 mg arms is the selection hole. strict_numeric on arm
    requires the ground-truth dose to be declared."""
    ch = ExportChannel(resolver=_DimResolver(arm="Duloxetine 60 mg"))
    vague = Claim("oocytes retrieved", 11.1, SourceTier.REGISTRY, "NCT03809429#om[1]",
                  meta={"outcome": "Number of Oocytes Retrieved", "arm": "Duloxetine",
                        "timepoint": "day of oocyte retrieval", "unit": "Oocytes"})
    with pytest.raises(ChannelViolation, match="wrong arm|arm="):
        ch.emit(vague)


def test_wrong_timepoint_week_is_blocked():
    """A numeric conflict in the timepoint (week 12 vs week 52) is blocked even though
    timepoint uses the lenient numeric rule (it blocks conflicts, allows omissions)."""
    ch = ExportChannel(resolver=_DimResolver(timepoint="week 52 follow-up"))
    wrong = Claim("oocytes retrieved", 11.1, SourceTier.REGISTRY, "NCT03809429#om[1]",
                  meta={"outcome": "Number of Oocytes Retrieved",
                        "arm": "GnRH Agonist (GONAPEPTYL)",
                        "timepoint": "week 12 follow-up", "unit": "Oocytes"})
    with pytest.raises(ChannelViolation, match="timepoint"):
        ch.emit(wrong)


def test_sanctioned_executor_enforced_when_required():
    """Codex round-4 executor seam: with require_sanctioned=True, an in-process stub
    (sanctioned=False, signed) is refused; only the real codex executor clears it."""
    stub = execute_prior_art_search(
        "X", ["q"],
        executor=lambda a, b: ([Candidate("adjacent", similar=False)], "codex", "openai"))
    assert stub.token_valid and stub.sanctioned is False
    c = Claim("X", 1, SourceTier.REGISTRY, "NCT1#a", claim_type=ClaimType.NOVELTY)
    # default (tests): stub passes the other checks
    guard_novelty(c, stub)
    # production posture: require the sanctioned cross-process executor -> stub refused
    with pytest.raises(PriorArtError, match="sanctioned"):
        guard_novelty(c, stub, require_sanctioned=True)


def test_sanctioned_flag_is_signed_not_forgeable():
    """Setting sanctioned=True by hand invalidates the token (it is in the signed
    payload) — a stub cannot forge sanctioned provenance."""
    stub = execute_prior_art_search(
        "X", ["q"],
        executor=lambda a, b: ([Candidate("adj", similar=False)], "codex", "openai"))
    forged = PriorArtSearch(subject=stub.subject, queries=stub.queries, sources=stub.sources,
                            reviewer_family=stub.reviewer_family, candidates=stub.candidates,
                            executed=True, token=stub.token, sanctioned=True)  # flipped
    assert forged.token_valid is False   # the token was signed over sanctioned=False


# --- round 5 re-attack: title-overlap arm, channel-boundary sanctioned ----------

def test_double_blind_arm_title_overlap_is_blocked():
    """Codex round-5: 'Double-Blind Tocilizumab' vs 'Double-Blind Placebo' shared
    {double, blind} (Jaccard 0.5) and false-accepted. Arm-boilerplate is now stripped
    so the drug/comparator name decides."""
    ch = ExportChannel(resolver=_DimResolver(arm="Double-Blind Tocilizumab"))
    right = Claim("oocytes retrieved", 11.1, SourceTier.REGISTRY, "NCT02453256#om[1]",
                  meta={"outcome": "Number of Oocytes Retrieved",
                        "arm": "Double-Blind Tocilizumab",
                        "timepoint": "day of oocyte retrieval", "unit": "Oocytes"})
    assert ch.emit(right).value == 11.1
    wrong = Claim("oocytes retrieved", 11.1, SourceTier.REGISTRY, "NCT02453256#om[1]",
                  meta={"outcome": "Number of Oocytes Retrieved",
                        "arm": "Double-Blind Placebo",
                        "timepoint": "day of oocyte retrieval", "unit": "Oocytes"})
    with pytest.raises(ChannelViolation, match="wrong arm|arm="):
        ch.emit(wrong)


def test_channel_blocks_stub_novelty_by_default():
    """Codex round-5: the channel called guard_novelty WITHOUT require_sanctioned, so a
    stub-backed NOVELTY emitted. Default channel now requires the sanctioned executor."""
    def stub(subject, queries):
        return [Candidate("adjacent", similar=False)], "codex", "openai"
    s = execute_prior_art_search("brand new method", ["q"], executor=stub)
    assert s.sanctioned is False
    c = Claim("brand new method", 3, SourceTier.REGISTRY, "NCT12345678#armcount=3",
              claim_type=ClaimType.NOVELTY,
              meta={"panel_verdict": "passed", "prior_art": s})
    with pytest.raises(ChannelViolation, match="sanctioned"):
        _chan().emit(c)   # default require_sanctioned_novelty=True


# --- round 6 re-attack: header bytes, WITH/WITHOUT, exact group_code -------------

def test_with_without_arm_negation_is_blocked():
    """Codex round-6: 'With Chronic Pain' was a strict subset of 'Without Chronic Pain'
    so containment accepted the negated arm. A negation mismatch now blocks."""
    ch = ExportChannel(resolver=_DimResolver(
        arm="Success in Phase 1 Among Participants Without Chronic Pain"))
    wrong = Claim("oocytes retrieved", 11.1, SourceTier.REGISTRY, "NCT00316277#om[1]",
                  meta={"outcome": "Number of Oocytes Retrieved",
                        "arm": "Success in Phase 1 Among Participants With Chronic Pain",
                        "timepoint": "day of oocyte retrieval", "unit": "Oocytes"})
    with pytest.raises(ChannelViolation, match="wrong arm|arm="):
        ch.emit(wrong)


def test_exact_group_code_binding_is_definitive():
    """Codex round-6 fix: declaring meta['group_code'] binds the arm by AACT's group
    code EXACTLY — no title heuristic. A wrong code blocks even if the title matches."""
    class _GResolver(LocatorResolver):
        def __init__(self): super().__init__(aact_path=None)
        def resolve(self, locator, claimed_value=None):
            if "om[" in (locator or ""):
                return Resolution(True, True, "stub",
                                  ground_truth={"value": 11.1, "title": "Number of Oocytes Retrieved",
                                                "group": "OG001", "arm": "Tocilizumab",
                                                "timepoint": "wk12", "unit": "Oocytes"})
            return Resolution(False, None, "stub")
    ch = ExportChannel(resolver=_GResolver())
    base = dict(outcome="Number of Oocytes Retrieved", arm="Tocilizumab",
                timepoint="wk12", unit="Oocytes")
    ok = Claim("oocytes retrieved", 11.1, SourceTier.REGISTRY, "NCT12345678#om[1]",
               meta={**base, "group_code": "OG001"})
    assert ch.emit(ok).value == 11.1
    wrong = Claim("oocytes retrieved", 11.1, SourceTier.REGISTRY, "NCT12345678#om[1]",
                  meta={**base, "group_code": "OG000"})   # wrong code, right title
    with pytest.raises(ChannelViolation, match="group.code|wrong arm"):
        ch.emit(wrong)


def test_write_report_refuses_header_with_a_number():
    """Codex round-6: the header was written UNSEALED — arbitrary bytes beside sealed
    Rendered lines. A header carrying a claim-shaped number is refused."""
    from overmind.gates.channel import write_report
    good = Claim("matched arm count", 3, SourceTier.REGISTRY, "NCT12345678#armcount=3")
    r = ExportChannel(resolver=_StubResolver()).emit(good)
    import tempfile, os as _os
    p = _os.path.join(tempfile.mkdtemp(), "r.md")
    with pytest.raises(ChannelViolation, match="header"):
        write_report(p, [r], header="fabricated mortality 38.1%")
    # a plain banner (no number) is fine
    write_report(p, [r], header="# Tuesday slides")


def test_scanner_surfaces_syntax_error_file(tmp_path):
    """Round-3 (Codex): a SyntaxError file is 'unparseable', never silently clean."""
    f = tmp_path / "broken.py"
    f.write_text("def run(:\n    print(1)\n", encoding="utf-8")
    rep = enforcement.scan_file(str(f))
    assert rep.parse_error and rep.status == "unparseable"


def test_scanner_flags_lax_channel_construction(tmp_path):
    """Round-3 (Codex): constructing a channel with resolution disabled is a bypass."""
    f = tmp_path / "lax.py"
    f.write_text("from overmind.gates.channel import ExportChannel\n"
                 "ch = ExportChannel(require_resolution=False)\n", encoding="utf-8")
    rep = enforcement.scan_file(str(f))
    assert any(s.kind == "gate_disabled" for s in rep.sites)


def test_write_report_sink_accepts_only_rendered():
    """Round-3 (agy asked for a channel-owned last mile): write_report refuses a raw
    value, accepts Rendered."""
    from overmind.gates.channel import write_report
    good = Claim("real arm count", 3, SourceTier.REGISTRY, "NCT12345678#armcount=3")
    rendered = _chan().emit(good)
    with pytest.raises(ChannelViolation, match="only Rendered"):
        write_report(str(__import__("tempfile").mktemp()), [rendered, 42])


def test_novelty_claim_through_channel_requires_signed_search():
    """The channel binds F7: a NOVELTY claim needs the signed search in meta, not
    just a panel verdict (Codex round-2 #3)."""
    c = Claim("brand new method", 3, SourceTier.REGISTRY, "NCT12345678#armcount=3",
              claim_type=ClaimType.NOVELTY,
              meta={"panel_verdict": "passed"})  # panel ok but NO prior_art
    with pytest.raises(ChannelViolation, match="PriorArtSearch|signature|prior"):
        _chan().emit(c)
    # attach a real signed search -> passes
    def stub(subject, queries):
        return [Candidate("adjacent", similar=False)], "codex", "openai"
    s = execute_prior_art_search("brand new method", ["q"], executor=stub)
    c2 = Claim("brand new method", 3, SourceTier.REGISTRY, "NCT12345678#armcount=3",
               claim_type=ClaimType.NOVELTY,
               meta={"panel_verdict": "passed", "prior_art": s})
    # stub search is sanctioned=False, so a production channel (require_sanctioned_novelty
    # default True) would block it; the stub path uses a channel that does not require it
    lax = ExportChannel(resolver=_StubResolver(), require_sanctioned_novelty=False)
    assert lax.emit(c2).value == 3


# --- enforcement scanner: the inventory is computed, not asserted -----------

def test_scanner_flags_a_naked_output(tmp_path):
    f = tmp_path / "naked_lane.py"
    f.write_text("def run(x):\n    print(f'the recall is {x}%')\n", encoding="utf-8")
    rep = enforcement.scan_file(str(f))
    assert rep.status == "OPEN-HOLE"
    assert any(s.kind == "output" for s in rep.sites)


def test_scanner_flags_raw_store_value_leak(tmp_path):
    f = tmp_path / "leaky.py"
    f.write_text("def run(fs, fid):\n    return fs.get(fid).value\n", encoding="utf-8")
    rep = enforcement.scan_file(str(f))
    assert any(s.kind == "store_value_leak" for s in rep.sites)


def test_scanner_treats_channel_user_as_routed(tmp_path):
    f = tmp_path / "routed.py"
    f.write_text("from overmind.gates.channel import emit\n"
                 "def run(claim):\n    print(emit(claim).text)\n", encoding="utf-8")
    rep = enforcement.scan_file(str(f))
    assert rep.gate_aware is True
    assert rep.status == "routed"


def test_routed_demo_lane_is_classified_routed():
    """The worked-example lane must itself be routed (dogfooding)."""
    import overmind.factstore.lanes.routed_emit as rl
    rep = enforcement.scan_file(rl.__file__)
    assert rep.gate_aware is True


# The known open holes as of Part III (2026-07-13), as PACKAGE-RELATIVE paths
# (not basenames — Codex flagged that `runner.py`/`__main__.py` collide). This is
# the RATCHET: a NEW file that reads world data and emits an un-routed number will
# not be on this list, so the test fails and forces a decision — route it, or
# consciously add it here with a reason. Shrinking this list is the retrofit
# backlog, in order.
_KNOWN_WORLD_HOLES = {
    "cli.py", "cluster/config_io.py", "core/orchestrator.py", "evidence/corpus.py",
    "evidence/screening.py", "factstore/__main__.py", "factstore/lanes/__main__.py",
    "factstore/lanes/known_bad.py", "factstore/lanes/other_lanes.py",
    "factstore/lanes/tuesday_demo.py", "factstore/seed_dta70.py",
    "factstore/seed_known_bad.py", "infra_invariants.py", "integrations/mcp_pin.py",
    "intelligence/research_benchmark.py", "nightly/runner.py", "verification/witnesses.py",
    # the demo lane's CLI reporter: its claim-emission (run() -> channel.emit) IS
    # routed, but main() prints per-case BLOCK reasons, and a blocked number has no
    # Rendered to route through. Listed honestly rather than gamed clean.
    "factstore/lanes/routed_emit.py",
}


def _package_dir():
    import os
    from overmind.gates import enforcement
    # enforcement.__file__ == .../overmind/overmind/gates/enforcement.py
    # dirname twice == .../overmind/overmind  (the package dir itself — NOT
    # .../overmind/overmind/overmind, which was the vacuous-scan bug Codex caught).
    return os.path.dirname(os.path.dirname(enforcement.__file__))


def test_ratchet_scans_a_real_nonempty_root():
    """Guard the guard: Codex round-2 caught the ratchet scanning a path that does
    not exist (vacuous pass). Prove the scanned root is real and non-empty."""
    import os
    from overmind.gates import enforcement
    pkg = _package_dir()
    assert os.path.isdir(pkg), pkg
    inv = enforcement.inventory([pkg])
    assert inv["files_with_emit"] > 10, (
        f"scanner found only {inv['files_with_emit']} emitting files — the root is "
        f"probably wrong again (the vacuous-scan bug).")


def test_no_new_world_claim_hole_ratchet():
    """The ratchet: no world-claim emitter may go unrouted unless it is a known,
    listed legacy hole. A new one turns the suite red — opt-in is now mandatory
    for anything added after Part III."""
    import os
    from overmind.gates import enforcement
    pkg = _package_dir()
    inv = enforcement.inventory([pkg])
    def rel(p):
        return os.path.relpath(p, pkg).replace(os.sep, "/")
    new_holes = [rel(p) for p in inv["world_claim_holes"] if rel(p) not in _KNOWN_WORLD_HOLES]
    assert not new_holes, (
        f"new unrouted world-claim emitter(s): {new_holes}. Route the number(s) "
        f"through overmind.gates.channel.emit, or (if truly not a number-to-user "
        f"path) add the file to _KNOWN_WORLD_HOLES with a reason.")


def test_ratchet_actually_catches_a_new_hole(tmp_path):
    """Prove the ratchet CAN fail (a gate that cannot be tripped is not a gate).
    Synthesise a new world-data emitter and confirm the scanner classifies it as a
    world-claim hole."""
    from overmind.gates import enforcement
    f = tmp_path / "new_lane.py"
    f.write_text(
        "import duckdb\n"
        "def run(nct):\n"
        "    con = duckdb.connect('aact.duckdb')\n"
        "    n = con.execute('select count(*) from design_groups').fetchone()[0]\n"
        "    print(f'arms: {n}')\n",
        encoding="utf-8")
    inv = enforcement.inventory([str(tmp_path)])
    assert any("new_lane.py" in p for p in inv["world_claim_holes"])


def test_leaky_file_is_not_credited_as_routed(tmp_path):
    """Codex round-2: importing the channel but still printing a raw number must NOT
    count as routed. It is 'leaky'."""
    from overmind.gates import enforcement
    f = tmp_path / "leaky_but_imports.py"
    f.write_text(
        "from overmind.gates.channel import emit\n"
        "def run(claim, raw):\n"
        "    print(emit(claim).text)\n"
        "    print(f'raw sneaks out: {raw}')\n",  # naked site despite the import
        encoding="utf-8")
    rep = enforcement.scan_file(str(f))
    assert rep.gate_aware is True
    assert rep.status == "leaky", rep.status
    assert len(rep.naked_sites) == 1


def test_routed_demo_lane_behaves():
    """End-to-end on the stub resolver: the real-shaped fabrications block, and a
    value-matched real claim would pass (uses the real AACT resolver if present)."""
    import overmind.factstore.lanes.routed_emit as rl
    rows = rl.run(channel=ExportChannel())  # default resolver (AACT if available)
    # regardless of AACT availability, every fabricated/synthetic/prose case blocks
    blocked = {r["claim"] for r in rows if r["outcome"] == "blocked"}
    assert "DTA70 fabricated sensitivity" in blocked
    assert "phantom trial arm count" in blocked
    assert "Xpert sensitivity" in blocked  # prose locator, no anchor
