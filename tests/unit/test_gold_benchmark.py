from __future__ import annotations

import json

import pytest

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
    assert rep["pooled_reviews"] >= 30
    assert rep["worst_pooled_logdev"] is not None and rep["worst_pooled_logdev"] < 0.02


def test_bcg_fixture_reproduces_within_tolerance():
    rep = run_gold_benchmark()
    bcg = next(r for r in rep["results"] if "BCG" in r["name"])
    assert bcg["kind"] == "pooled" and bcg["pass"]
    gating = [c for c in bcg["comparisons"] if c["tol"] is not None]
    assert gating and all(c["pass"] for c in gating)


def test_scope_note_separates_engine_from_cochrane_correctness():
    """The report must state it validates the ENGINE, not the Cochrane reviews."""
    rep = run_gold_benchmark()
    note = rep.get("scope_note", "")
    assert "ENGINE" in note and "not certify" in note.lower()
    assert "fragile" in note.lower()  # Cochrane reviews are themselves fragile


def test_cochrane_reproduction_fails_closed_on_missing_paths(tmp_path):
    """Opt-in corpus runner returns an error (never crashes / never fakes) when the
    data dir or reference csv is absent."""
    from overmind.intelligence.gold_benchmark import cochrane_reproduction
    r = cochrane_reproduction(tmp_path / "nope", tmp_path / "missing.csv")
    assert "error" in r
    # with a real (empty) csv but missing data dir, still errors
    (tmp_path / "ref.csv").write_text("review_id,analysis_number,k,mf_theta\n", encoding="utf-8")
    r2 = cochrane_reproduction(tmp_path / "nope", tmp_path / "ref.csv")
    assert "error" in r2


def test_cochrane_reproduction_accept_logic(tmp_path, monkeypatch):
    """The opt-in corpus runner must: (1) only count a candidate whose study count == ref k
    (cardinality guard blocks coincidental wrong-cardinality matches); (2) only count a match
    within tol; (3) build the denominator (total) independently of acceptance."""
    pd = pytest.importorskip("pandas")
    import pyreadr
    from overmind.evidence.pooling import Study, pool
    from overmind.intelligence.gold_benchmark import cochrane_reproduction

    # one analysis, 2 binary studies; reference theta = the engine's own REML pooled value
    studies = [Study(ai=10, n1=100, ci=20, n2=100), Study(ai=15, n1=120, ci=25, n2=130)]
    theta = pool(studies, measure="RR", method="REML")["estimate_log"]
    df = pd.DataFrame([
        {"Analysis.number": 1, "Study": "A", "Experimental.cases": 10, "Experimental.N": 100,
         "Control.cases": 20, "Control.N": 100, "GIV.Mean": float("nan"), "GIV.SE": float("nan"),
         "Experimental.mean": float("nan"), "Experimental.SD": float("nan"),
         "Control.mean": float("nan"), "Control.SD": float("nan"), "Subgroup.number": float("nan")},
        {"Analysis.number": 1, "Study": "B", "Experimental.cases": 15, "Experimental.N": 120,
         "Control.cases": 25, "Control.N": 130, "GIV.Mean": float("nan"), "GIV.SE": float("nan"),
         "Experimental.mean": float("nan"), "Experimental.SD": float("nan"),
         "Control.mean": float("nan"), "Control.SD": float("nan"), "Subgroup.number": float("nan")},
    ])
    monkeypatch.setattr(pyreadr, "read_r", lambda path: {"d": df})
    (tmp_path / "CD0001_pub1_data.rda").write_text("stub", encoding="utf-8")

    def _ref(k, ref_theta):
        p = tmp_path / f"ref_{k}_{ref_theta:.4f}.csv"
        p.write_text("review_id,analysis_number,k,mf_theta,effect_type\n"
                     f"CD0001_pub1,1,{k},{ref_theta},logRR\n", encoding="utf-8")
        return cochrane_reproduction(tmp_path, p)

    # (1) correct k + within tol -> matched
    r = _ref(2, theta)
    assert r["exact_reproductions"] == 1 and r["references_total"] == 1
    # (2) wrong cardinality (k=3) but SAME theta -> cardinality guard blocks it
    r = _ref(3, theta)
    assert r["exact_reproductions"] == 0 and r["references_total"] == 1
    # (3) correct k but theta far outside tol -> counted in denominator, not matched
    r = _ref(2, theta + 0.5)
    assert r["exact_reproductions"] == 0 and r["references_total"] == 1
    assert r["median_deviation"] is None


def test_erroring_fixture_fails_closed(tmp_path):
    """A malformed / unknown fixture must FAIL (never a silent skip)."""
    (tmp_path / "bad.json").write_text(json.dumps({"kind": "pooled", "studies": []}), encoding="utf-8")
    (tmp_path / "unknown.json").write_text(json.dumps({"kind": "mystery"}), encoding="utf-8")
    rep = run_gold_benchmark(gold_dir=tmp_path)
    assert rep["fixtures_total"] == 2
    assert rep["fixtures_passed"] == 0
    assert rep["all_passed"] is False
    assert all(r["pass"] is False for r in rep["results"])
