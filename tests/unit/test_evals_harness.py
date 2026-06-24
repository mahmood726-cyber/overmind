"""Regression coverage for the evals/ measurement harness.

These assert the *structural* contract and the key truth-first invariants — NOT
inflated targets. They lock in that:
  * the SpecBench-style held-out witness catches every reward-hack a visible-only
    verifier would falsely certify,
  * the judge degenerate-guard never lets a master-key input become a PASS, and
    never misflags a genuine verdict,
  * the memory store recalls the current fact and suppresses superseded ones,
    with a counterfactual proving the temporal filter (not keyword luck) does it.

If a future change loosens any of these, a test here fails — by design.
"""
from __future__ import annotations

from evals import (
    engine_routing,
    judge_cot_goldenset,
    judge_masterkey,
    memory_recall,
    quorum_decorrelation,
    specbench_style,
)


def test_specbench_style_heldout_catches_reward_hacks():
    payload = specbench_style.evaluate()
    rh = payload["reward_hack"]
    # Every constructed reward-hack passes the visible set...
    assert rh["passed_visible"] == rh["n"] == 5
    # ...and the held-out witness catches all of them (Overmind's held-out policy).
    assert rh["caught_by_heldout"] == rh["passed_visible"]
    assert rh["heldout_catch_rate"] == 1.0
    # A visible-only verifier would have falsely certified every one.
    assert rh["visible_only_false_certifications"] == 5
    # The reward-hacking gap is strictly positive (validation overstates correctness).
    assert payload["specbench_gap"] > 0.0


def test_judge_masterkey_guard_holds():
    payload = judge_masterkey.evaluate()
    # No degenerate / master-key input may ever become an effective PASS.
    assert payload["degenerate"]["false_pass_rate"] == 0.0
    # Genuine verdicts classified correctly and never misflagged as degenerate.
    assert payload["genuine"]["accuracy"] == 1.0
    assert payload["genuine"]["misflagged_as_degenerate"] == 0
    # #2d input-side tamper guard: the original planted-VERDICT cases and the
    # extra signature-bearing ones no longer become an effective PASS.
    assert payload["injection_boundary"]["false_pass_rate"] == 0.0
    assert payload["injection_signature"]["false_pass_rate"] == 0.0
    # HONEST: a clean planted PASS (no attack phrase) is still an open boundary —
    # output scanning cannot catch it. We assert it leaks so the limit stays
    # visible and is not silently "fixed" by an over-broad guard.
    assert payload["injection_clean_boundary"]["false_pass_rate"] == 1.0


def test_memory_recall_suppresses_superseded():
    payload = memory_recall.evaluate()
    assert payload["recall"] == 1.0
    assert payload["stale_suppression_rate"] == 1.0
    # The defense is the temporal filter: a naive search WOULD leak the stale fact.
    assert payload["naive_stale_leak_rate"] == 1.0
    assert payload["expired_probe"]["expired_fact_suppressed"] is True


def test_quorum_decorrelation_enforcement_eliminates_overcount():
    payload = quorum_decorrelation.evaluate()
    c = payload["correlated_panels"]
    # Before enforcement every correlated panel overcounts its independence...
    assert c["overcount_rate_before"] == 1.0
    # ...after hard enforcement none does (repaired to one-per-family or rejected).
    assert c["overcount_rate_after"] == 0.0
    # Honest (all-distinct) panels are left untouched — no regression.
    assert payload["honest_panels"]["unchanged_rate"] == 1.0


def test_engine_routing_cuts_expensive_invocations_without_losing_accuracy():
    payload = engine_routing.evaluate()
    # Routing invokes the expensive tier on strictly fewer than all cases...
    assert payload["expensive_invocation_rate_after"] < payload["expensive_invocation_rate_before"]
    # ...while preserving accuracy vs always-expensive (truth-first guard)...
    assert payload["accuracy"]["routed_preserves_expensive"] is True
    assert payload["accuracy"]["routed"] == payload["accuracy"]["always_expensive"]
    # ...and every routing decision matched its expected escalate/accept label.
    assert payload["routing_decisions_match_expectation"] is True


def test_cot_goldenset_gate_passes_no_regression():
    payload = judge_cot_goldenset.evaluate()
    # CoT on vs off classify the golden set identically (parser/guard untouched).
    assert payload["parse_agreement_rate"] == 1.0
    # Degenerate guard still holds with CoT on; rubric + output contract intact.
    assert payload["degenerate"]["cot_on_false_pass_rate"] == 0.0
    assert payload["cot_prompt_structural"]["rubric_present"] is True
    assert payload["cot_prompt_structural"]["output_contract_present"] is True
    assert payload["no_regression"] is True
    # Truth-first: we do NOT claim a measured quality gain here.
    assert payload["quality_delta_measured"] is False
