"""Tests for the cost-per-accepted-change instrument (T12b / WORLD_CLASS_SPEC D5)."""
from __future__ import annotations

import json

import pytest

from overmind.telemetry.cost_accounting import (
    BREAK_EVEN_ACCEPTANCE,
    CostEvent,
    CostLedger,
    aggregate_events,
    cost_event_from_output,
    estimate_usd,
    parse_claude_json_cost,
)


# --- parse_claude_json_cost -----------------------------------------------------

def test_parse_whole_json_object():
    raw = json.dumps({
        "type": "result",
        "total_cost_usd": 0.0123,
        "usage": {"input_tokens": 1500, "output_tokens": 300},
    })
    ev = parse_claude_json_cost(raw, loop="methods", label="task1")
    assert ev is not None
    assert ev.measured is True
    assert ev.usd == pytest.approx(0.0123)
    assert ev.input_tokens == 1500
    assert ev.output_tokens == 300
    assert ev.loop == "methods"


def test_parse_json_on_last_line_of_stream():
    raw = "some banner\nprogress...\n" + json.dumps({"total_cost_usd": 0.5, "usage": {}})
    ev = parse_claude_json_cost(raw)
    assert ev is not None
    assert ev.usd == 0.5
    assert ev.measured is True


def test_parse_cost_usd_alias():
    ev = parse_claude_json_cost(json.dumps({"cost_usd": 0.02}))
    assert ev is not None and ev.usd == pytest.approx(0.02)


def test_parse_returns_none_without_cost_field():
    assert parse_claude_json_cost(json.dumps({"foo": "bar"})) is None


def test_parse_returns_none_on_garbage():
    assert parse_claude_json_cost("not json at all") is None
    assert parse_claude_json_cost("") is None


def test_parse_bad_cost_value_returns_none():
    assert parse_claude_json_cost(json.dumps({"total_cost_usd": "abc"})) is None


# --- estimate_usd ---------------------------------------------------------------

def test_estimate_usd_known_engine():
    # claude: (3, 15) per Mtok
    usd = estimate_usd("claude", 1_000_000, 1_000_000)
    assert usd == pytest.approx(18.0)


def test_estimate_usd_unknown_engine_uses_fallback():
    usd = estimate_usd("mystery", 1_000_000, 0)
    assert usd == pytest.approx(2.0)


def test_estimate_usd_local_is_free():
    assert estimate_usd("local", 5_000_000, 5_000_000) == 0.0


# --- CostLedger economics -------------------------------------------------------

def test_cost_per_accepted_change():
    ledger = CostLedger()
    ledger.add_cost(CostEvent(loop="L", engine="claude", usd=1.0, measured=True))
    ledger.add_cost(CostEvent(loop="L", engine="claude", usd=1.0, measured=True))
    ledger.record_decision(True, loop="L")
    ledger.record_decision(True, loop="L")
    ledger.record_decision(False, loop="L")
    econ = ledger.economics("L")
    assert econ.total_usd == pytest.approx(2.0)
    assert econ.accepted == 2
    assert econ.rejected == 1
    assert econ.cost_per_accepted_change == pytest.approx(1.0)  # $2 / 2 accepted
    assert econ.acceptance_rate == pytest.approx(2 / 3)


def test_below_break_even_heuristic():
    ledger = CostLedger()
    ledger.add_cost(CostEvent(loop="L", engine="claude", usd=5.0, measured=True))
    # 1 accepted / 4 decisions = 0.25 < 0.5
    ledger.record_decision(True, loop="L")
    for _ in range(3):
        ledger.record_decision(False, loop="L")
    econ = ledger.economics("L")
    assert econ.acceptance_rate == pytest.approx(0.25)
    assert econ.below_break_even is True
    assert BREAK_EVEN_ACCEPTANCE == 0.5


def test_above_break_even():
    ledger = CostLedger()
    ledger.record_decision(True, loop="L")
    ledger.record_decision(True, loop="L")
    ledger.record_decision(False, loop="L")
    assert ledger.economics("L").below_break_even is False


def test_no_decisions_yields_none_metrics():
    ledger = CostLedger()
    ledger.add_cost(CostEvent(loop="L", engine="claude", usd=1.0, measured=True))
    econ = ledger.economics("L")
    assert econ.acceptance_rate is None
    assert econ.cost_per_accepted_change is None
    assert econ.below_break_even is None


def test_measured_vs_estimated_split():
    ledger = CostLedger()
    ledger.add_cost(CostEvent(loop="L", engine="claude", usd=2.0, measured=True))
    ledger.add_usage_estimate("codex", 1_000_000, 0, loop="L")  # estimate: $2.5
    econ = ledger.economics("L")
    assert econ.measured_usd == pytest.approx(2.0)
    assert econ.estimated_usd == pytest.approx(2.5)
    assert econ.total_usd == pytest.approx(4.5)


def test_add_claude_json_measured():
    ledger = CostLedger()
    ev = ledger.add_claude_json(json.dumps({"total_cost_usd": 0.3, "usage": {}}), loop="L")
    assert ev.measured is True and ev.usd == pytest.approx(0.3)
    assert ledger.economics("L").measured_usd == pytest.approx(0.3)


def test_add_claude_json_unparseable_still_counts():
    ledger = CostLedger()
    ev = ledger.add_claude_json("garbage", loop="L")
    assert ev.measured is False
    assert ledger.economics("L").cost_events == 1


def test_overall_vs_per_loop():
    ledger = CostLedger()
    ledger.add_cost(CostEvent(loop="A", engine="claude", usd=1.0, measured=True))
    ledger.add_cost(CostEvent(loop="B", engine="codex", usd=3.0, measured=True))
    ledger.record_decision(True, loop="A")
    ledger.record_decision(True, loop="B")
    overall = ledger.economics()
    assert overall.total_usd == pytest.approx(4.0)
    assert overall.accepted == 2
    assert set(ledger.loops()) == {"A", "B"}
    report = ledger.report()
    assert report["overall"]["total_usd"] == pytest.approx(4.0)
    assert "A" in report["loops"] and "B" in report["loops"]


def test_jsonl_persistence(tmp_path):
    path = tmp_path / "cost.jsonl"
    ledger = CostLedger(jsonl_path=path)
    ledger.add_cost(CostEvent(loop="L", engine="claude", usd=1.0, measured=True))
    ledger.record_decision(True, loop="L")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    kinds = [json.loads(ln)["kind"] for ln in lines]
    assert kinds == ["cost", "decision"]


def test_cost_event_from_output_measured():
    lines = ["progress line", json.dumps({"total_cost_usd": 0.07, "usage": {"output_tokens": 50}})]
    ev = cost_event_from_output(lines, loop="L", label="t")
    assert ev.measured is True
    assert ev.usd == pytest.approx(0.07)
    assert ev.loop == "L"


def test_cost_event_from_output_estimated_fallback():
    ev = cost_event_from_output(["just some interactive output", "no json here"], engine="claude", loop="L")
    assert ev.measured is False
    assert ev.output_tokens > 0
    assert ev.usd >= 0.0
    assert ev.label == "estimated_from_output"


def test_cost_event_from_output_empty():
    ev = cost_event_from_output([], loop="L")
    assert ev.measured is False
    assert ev.output_tokens == 0


def test_cost_event_from_string():
    ev = cost_event_from_output(json.dumps({"total_cost_usd": 0.01}), loop="L")
    assert ev.measured is True and ev.usd == pytest.approx(0.01)


def test_ledger_accept_flow_from_output():
    # simulate two accepts (measured) + one reject (estimated) on one loop
    ledger = CostLedger()
    ledger.add_cost(cost_event_from_output([json.dumps({"total_cost_usd": 1.0})], loop="P"))
    ledger.record_decision(True, loop="P")
    ledger.add_cost(cost_event_from_output([json.dumps({"total_cost_usd": 1.0})], loop="P"))
    ledger.record_decision(True, loop="P")
    ledger.add_cost(cost_event_from_output(["noise"], loop="P"))
    ledger.record_decision(False, loop="P")
    econ = ledger.economics("P")
    assert econ.accepted == 2
    assert econ.cost_per_accepted_change == pytest.approx(econ.total_usd / 2)
    assert econ.measured_usd == pytest.approx(2.0)


def test_aggregate_events():
    events = [
        CostEvent(loop="X", engine="claude", usd=1.0, measured=True),
        CostEvent(loop="Y", engine="codex", usd=2.0, measured=False),
    ]
    econ = aggregate_events(events)
    assert econ.total_usd == pytest.approx(3.0)
    assert econ.measured_usd == pytest.approx(1.0)
    assert econ.estimated_usd == pytest.approx(2.0)
