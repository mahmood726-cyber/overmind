from __future__ import annotations

import json

from overmind.intelligence.gold_benchmark import run_gold_benchmark


def test_committed_gold_fixtures_all_pass():
    """The real, cited gold fixtures must reproduce their published references
    within the stated tolerance — the measured output-correctness gate."""
    rep = run_gold_benchmark()
    assert rep["benchmark_type"] == "gold_standard_output_correctness"
    assert rep["fixtures_total"] >= 2
    assert rep["all_passed"] is True, [r for r in rep["results"] if not r["pass"]]
    # multiple real pooled reviews (BCG variants + real Cochrane reviews vs metafor),
    # all reproduced tightly
    assert rep["pooled_reviews"] >= 10
    assert rep["worst_pooled_logdev"] is not None and rep["worst_pooled_logdev"] < 0.02


def test_bcg_fixture_reproduces_within_tolerance():
    rep = run_gold_benchmark()
    bcg = next(r for r in rep["results"] if "BCG" in r["name"])
    assert bcg["kind"] == "pooled" and bcg["pass"]
    gating = [c for c in bcg["comparisons"] if c["tol"] is not None]
    assert gating and all(c["pass"] for c in gating)


def test_erroring_fixture_fails_closed(tmp_path):
    """A malformed / unknown fixture must FAIL (never a silent skip)."""
    (tmp_path / "bad.json").write_text(json.dumps({"kind": "pooled", "studies": []}), encoding="utf-8")
    (tmp_path / "unknown.json").write_text(json.dumps({"kind": "mystery"}), encoding="utf-8")
    rep = run_gold_benchmark(gold_dir=tmp_path)
    assert rep["fixtures_total"] == 2
    assert rep["fixtures_passed"] == 0
    assert rep["all_passed"] is False
    assert all(r["pass"] is False for r in rep["results"])
