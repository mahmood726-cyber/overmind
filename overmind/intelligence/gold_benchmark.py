"""Gold-standard task benchmark — MEASURED output-correctness of the synthesis path.

The capability_evidence_benchmark (research_benchmark.py) scores capability
PRESENCE. This scores capability CORRECTNESS: it runs the real pooling engine
(evidence/pooling.py) and PRISMA accounting (evidence/prisma.py) on committed,
cited gold fixtures and checks the output against the published/declared reference
within a stated tolerance. No fabricated references: every fixture carries its
source. Fail-closed: a fixture that errors is a FAILURE, never a silent skip.

Fixtures live in evidence/data/gold_reviews/*.json. Two kinds:
  - "pooled": raw study data + a published pooled estimate -> reproduce within tol.
  - "prisma": per-record screening decisions + declared flow counts -> reconcile.

Deterministic, offline, stdlib-only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from overmind.evidence.pooling import Study, pool

_GOLD_DIR = Path(__file__).resolve().parent.parent / "evidence" / "data" / "gold_reviews"


def _abs(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return abs(a - b)


def _score_pooled(fix: dict) -> dict:
    measure = fix.get("measure", "RR")
    method = fix.get("method", "PM")
    studies = [Study(**s) for s in fix["studies"]]
    got = pool(studies, measure=measure, method=method)
    ref = fix["reference"]
    tol = fix.get("tolerance", {})

    comparisons: list[dict] = []

    def cmp(metric: str, got_val, ref_val, tol_key: str):
        t = tol.get(tol_key)
        dev = _abs(got_val, ref_val)
        ok = (t is None) or (dev is not None and dev <= t)
        comparisons.append({"metric": metric, "got": got_val, "ref": ref_val,
                            "abs_dev": dev, "tol": t, "pass": ok})

    cmp("estimate_log", got["estimate_log"], ref.get("estimate_log"), "estimate_log")
    cmp("se", got["se"], ref.get("se"), "se")
    if ref.get("ci_log") and tol.get("ci_log") is not None:
        ci_dev = max(abs(got["ci_log"][0] - ref["ci_log"][0]),
                     abs(got["ci_log"][1] - ref["ci_log"][1]))
        comparisons.append({"metric": "ci_log", "got": got["ci_log"], "ref": ref["ci_log"],
                            "abs_dev": ci_dev, "tol": tol["ci_log"], "pass": ci_dev <= tol["ci_log"]})
    cmp("tau2", got["tau2"], ref.get("tau2"), "tau2")
    cmp("I2_percent", got["I2_percent"], ref.get("I2_percent"), "I2_percent")

    # Only metrics with a declared tolerance gate the verdict (others are reported).
    gating = [c for c in comparisons if c["tol"] is not None]
    passed = all(c["pass"] for c in gating)
    return {
        "kind": "pooled", "measure": measure, "method": method, "k": got["k"],
        "pass": passed,
        "estimate_log": got["estimate_log"], "estimate_ratio": got["estimate_ratio"],
        "comparisons": comparisons,
        "headline_logdev": _abs(got["estimate_log"], ref.get("estimate_log")),
    }


def _get_dotted(d: dict, dotted: str):
    cur: Any = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _score_prisma(fix: dict) -> dict:
    from overmind.evidence.prisma import prisma_flow
    flow = prisma_flow(fix["records"])
    expected = fix["expected"]
    rows: list[dict] = []
    for key, want in expected.items():
        got = _get_dotted(flow, key)
        rows.append({"bucket": key, "got": got, "expected": want, "pass": got == want})
    passed = all(r["pass"] for r in rows)
    return {"kind": "prisma", "pass": passed, "buckets": rows}


def run_gold_benchmark(gold_dir: Path | None = None) -> dict:
    """Run every gold fixture; return a measured output-correctness report."""
    gdir = Path(gold_dir) if gold_dir else _GOLD_DIR
    results: list[dict] = []
    for path in sorted(gdir.glob("*.json")):
        fix: dict | None = None
        try:
            fix = json.loads(path.read_text(encoding="utf-8"))
            kind = fix.get("kind")
            if kind == "pooled":
                r = _score_pooled(fix)
            elif kind == "prisma":
                r = _score_prisma(fix)
            else:
                r = {"kind": kind, "pass": False, "error": f"unknown fixture kind {kind!r}"}
        except Exception as exc:  # noqa: BLE001 - fail closed: an erroring fixture FAILS
            r = {"kind": "error", "pass": False, "error": f"{type(exc).__name__}: {exc}"}
        r["fixture"] = path.name
        r["name"] = (fix.get("name") if isinstance(fix, dict) else None) or path.name
        r["citation"] = fix.get("citation") if isinstance(fix, dict) else None
        results.append(r)

    pooled = [r for r in results if r.get("kind") == "pooled"]
    n_pass = sum(1 for r in results if r.get("pass"))
    worst_logdev = max((r["headline_logdev"] for r in pooled
                        if r.get("headline_logdev") is not None), default=None)
    return {
        "benchmark_type": "gold_standard_output_correctness",
        "fixtures_total": len(results),
        "fixtures_passed": n_pass,
        "all_passed": len(results) > 0 and n_pass == len(results),
        "pooled_reviews": len(pooled),
        "worst_pooled_logdev": worst_logdev,
        "policy": "measured against committed cited references within stated tolerance; an erroring fixture fails closed (never a silent skip)",
        "results": results,
    }
