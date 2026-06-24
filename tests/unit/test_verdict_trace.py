"""Unit tests for the verdict-pipeline span tracer (#3c, observability)."""
from __future__ import annotations

import pytest

from overmind.verification.verdict_trace import VerdictTracer
from overmind.verification.cert_bundle import Arbitrator
from overmind.verification.scope_lock import WitnessResult


def _wr(wt, verdict):
    return WitnessResult(witness_type=wt, verdict=verdict, exit_code=0,
                         stdout="", stderr="", elapsed=0.1)


def test_span_records_parent_child_and_closes():
    t = VerdictTracer()
    with t.span("parent", tokens=10):
        with t.span("child", tokens=5):
            pass
    spans = {s.name: s for s in t.spans}
    assert spans["parent"].parent_id is None
    assert spans["child"].parent_id == spans["parent"].span_id
    assert all(s.end_ns is not None for s in t.spans)
    assert t.is_tree_consistent() is True
    assert t.total_tokens() == 15


def test_span_coverage_partial_and_full():
    t = VerdictTracer()
    with t.span("witness:smoke"):
        pass
    # 'judge' and 'arbitrator' not emitted yet (coverage rounded to 4dp by design)
    assert t.span_coverage(["witness", "judge", "arbitrator"]) == 0.3333
    with t.span("judge"):
        pass
    with t.span("arbitrator"):
        pass
    assert t.span_coverage(["witness", "judge", "arbitrator"]) == 1.0


def test_span_records_error_status_and_reraises():
    t = VerdictTracer()
    with pytest.raises(ValueError):
        with t.span("boom"):
            raise ValueError("x")
    span = t.spans[0]
    assert span.status.startswith("error:ValueError")
    assert span.end_ns is not None  # still closed


def test_arbitrator_emits_span_when_traced():
    t = VerdictTracer()
    results = [_wr("test_suite", "PASS"), _wr("smoke", "PASS")]
    verdict, _ = Arbitrator().arbitrate(results, tracer=t)
    assert verdict == "CERTIFIED"
    arb = [s for s in t.spans if s.name == "arbitrator"]
    assert len(arb) == 1
    assert arb[0].attributes.get("verdict") == "CERTIFIED"
    assert arb[0].attributes.get("witnesses") == 2


def test_arbitrator_untraced_is_unchanged():
    # No tracer -> identical verdict, no spans, zero behavior change.
    results = [_wr("test_suite", "PASS"), _wr("smoke", "FAIL")]
    v1, r1 = Arbitrator().arbitrate(results)
    v2, r2 = Arbitrator().arbitrate(results, tracer=None)
    assert (v1, r1) == (v2, r2) == ("REJECT", r1)


def test_tree_inconsistent_when_span_open():
    t = VerdictTracer()
    cm = t.span("never_closed")
    cm.__enter__()
    # span opened but not closed -> inconsistent
    assert t.is_tree_consistent() is False
