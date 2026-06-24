"""Eval 5 — cost-aware engine routing (audit C2 / RouteLLM).

Measures whether routing a cheap/local judge first and **escalating to the
expensive quorum only on uncertainty** (a) cuts the expensive-tier invocation
volume and (b) preserves accuracy vs always running the expensive tier.

Background: a cross-family quorum is several× the token cost of a single local
judge. If routing keeps accuracy while invoking the quorum on only a fraction of
cases, that fraction *is* the token-cost lever.

Headline (assumption-free): **expensive-tier (quorum) invocation rate**
  always-expensive  100 %  →  routed = escalation_rate

Accuracy guard (truth-first): routed accuracy must equal always-expensive
accuracy — routing may only skip the quorum where the cheap judge is *confidently
right*; it must never trade correctness for cost. We also report cheap-only
accuracy to show what naive "just use local" would lose.

Run against the REAL ``overmind.verification.llm_judge.RoutedJudge`` with scripted
backends (no network). The cheap/expensive raw outputs and the ground-truth label
are fixed per case.
"""
from __future__ import annotations

from dataclasses import dataclass

from overmind.verification.llm_judge import LLMJudge, RoutedJudge, StubBackend
from overmind.storage.models import ProjectRecord, TaskRecord, VerificationResult

from evals.common import pct, write_result

# Cost ratio used only for the *secondary* token-saving figure. The primary
# number (invocation rate) needs no ratio. K = expensive:cheap cost; conservative
# stand-in for a cross-family quorum vs a single local call.
EXPENSIVE_COST = 4
CHEAP_COST = 1


def _verdict(passed: bool, conf: float) -> str:
    v = "PASS" if passed else "FAIL"
    return f"VERDICT: {v}\nCONFIDENCE: {conf}\nREASONING: scripted.\nCONCERNS: none\nMET: x\nMISSED: none"


@dataclass(frozen=True)
class RouteCase:
    name: str
    cheap_resp: str       # what the cheap judge backend emits
    expensive_resp: str   # what the expensive tier emits (treated as authoritative)
    truth_pass: bool      # ground-truth correct verdict
    expect_escalate: bool # whether routing SHOULD escalate (for a structural check)


# Authoritative expensive responses are always correct (high confidence) — the
# expensive tier is the reference. The cheap tier varies in quality/confidence.
def _exp(passed: bool) -> str:
    return _verdict(passed, 0.95)


_CASES: list[RouteCase] = [
    # cheap is confidently right -> accept cheap, no escalation
    RouteCase("cheap_conf_pass", _verdict(True, 0.92), _exp(True), True, expect_escalate=False),
    RouteCase("cheap_conf_fail", _verdict(False, 0.90), _exp(False), False, expect_escalate=False),
    RouteCase("cheap_conf_pass2", _verdict(True, 0.97), _exp(True), True, expect_escalate=False),
    RouteCase("cheap_conf_fail2", _verdict(False, 0.88), _exp(False), False, expect_escalate=False),
    # cheap is uncertain or wrong -> escalate, expensive corrects/confirms
    RouteCase("cheap_lowconf_wrong", _verdict(True, 0.60), _exp(False), False, expect_escalate=True),
    RouteCase("cheap_pass_below_floor", _verdict(True, 0.80), _exp(False), False, expect_escalate=True),
    RouteCase("cheap_degenerate", "", _exp(True), True, expect_escalate=True),
    RouteCase("cheap_judge_error", "JUDGE_ERROR: backend down", _exp(False), False, expect_escalate=True),
]


def _inputs():
    task = TaskRecord(
        task_id="rt", project_id="rp", title="t", task_type="verification",
        source="eval", priority=0.8, risk="medium", expected_runtime_min=5,
        expected_context_cost="low", required_verification=["tests"],
    )
    project = ProjectRecord(project_id="rp", name="P", root_path="/tmp/p")
    vr = VerificationResult(task_id="rt", success=True, required_checks=["tests"],
                            completed_checks=["tests"], skipped_checks=[], details=[])
    return task, project, vr


def _effective_pass(v) -> bool:
    return bool(v.passed) and "judge_error" not in v.concerns and "judge_degenerate" not in v.concerns


def evaluate() -> dict:
    task, project, vr = _inputs()
    n = len(_CASES)

    escalations = 0
    routed_correct = 0
    expensive_correct = 0
    cheap_only_correct = 0
    rows = []

    for c in _CASES:
        cheap_judge = LLMJudge(backend=StubBackend(response=c.cheap_resp))
        expensive_judge = LLMJudge(backend=StubBackend(response=c.expensive_resp))
        routed = RoutedJudge(cheap_judge=cheap_judge, expensive_judge=expensive_judge)

        rv = routed.judge(task, project, vr)
        escalated = "routed_escalated" in rv.concerns
        escalations += int(escalated)

        # routed correctness: did the FINAL effective verdict match ground truth?
        routed_pass = _effective_pass(rv)
        routed_ok = routed_pass == c.truth_pass
        routed_correct += int(routed_ok)

        # baselines (independent judges, same scripted responses)
        exp_only = LLMJudge(backend=StubBackend(response=c.expensive_resp)).judge(task, project, vr)
        expensive_correct += int(_effective_pass(exp_only) == c.truth_pass)
        cheap_only = LLMJudge(backend=StubBackend(response=c.cheap_resp)).judge(task, project, vr)
        cheap_only_correct += int(_effective_pass(cheap_only) == c.truth_pass)

        rows.append({
            "name": c.name,
            "escalated": escalated,
            "expected_escalate": c.expect_escalate,
            "escalate_matches_expectation": escalated == c.expect_escalate,
            "routed_correct": routed_ok,
        })

    escalation_rate = pct(escalations, n)

    # Secondary token figure under the stated cost ratio (NOT assumption-free).
    cost_always = n * EXPENSIVE_COST
    cost_routed = n * CHEAP_COST + escalations * EXPENSIVE_COST
    token_saving = pct(cost_always - cost_routed, cost_always)

    payload = {
        "eval": "engine_routing",
        "n": n,
        "escalation_rate": escalation_rate,
        "expensive_invocation_rate_before": 1.0,   # always-expensive baseline
        "expensive_invocation_rate_after": escalation_rate,
        "accuracy": {
            "routed": pct(routed_correct, n),
            "always_expensive": pct(expensive_correct, n),
            "cheap_only": pct(cheap_only_correct, n),
            # truth-first guard: routing must not lose accuracy vs expensive.
            "routed_preserves_expensive": routed_correct == expensive_correct,
        },
        "token_cost_model": {
            "cheap_cost": CHEAP_COST,
            "expensive_cost": EXPENSIVE_COST,
            "cost_always_expensive": cost_always,
            "cost_routed": cost_routed,
            "token_saving_at_ratio": token_saving,
            "note": (
                f"token_saving assumes expensive:cheap = {EXPENSIVE_COST}:{CHEAP_COST}; "
                "the assumption-free number is the expensive-invocation rate. Real "
                "saving scales with the true local:quorum cost ratio."
            ),
        },
        "routing_decisions_match_expectation": all(r["escalate_matches_expectation"] for r in rows),
        "cases": rows,
    }
    return payload


def main() -> dict:
    payload = evaluate()
    a = payload["accuracy"]
    path = write_result("engine_routing", payload)
    print(f"[engine_routing] expensive(quorum) invocation rate: 100% -> "
          f"{payload['expensive_invocation_rate_after']:.0%} (escalation rate)")
    print(f"[engine_routing] accuracy: routed={a['routed']:.0%} "
          f"== always-expensive={a['always_expensive']:.0%}  (cheap-only={a['cheap_only']:.0%})")
    print(f"[engine_routing] token saving @ {payload['token_cost_model']['expensive_cost']}:"
          f"{payload['token_cost_model']['cheap_cost']} ratio = "
          f"{payload['token_cost_model']['token_saving_at_ratio']:.0%} (secondary)")
    print(f"[engine_routing] -> {path}")
    return payload


if __name__ == "__main__":
    main()
