"""NMA assumption-checker (Phase 3 / #5) — verify the assumptions a network
meta-analysis makes, rather than just running one.

The differentiator vs automate-only NMA agents (e.g. MetaMind): they pick a
model and produce rankings; this *checks* the methodological preconditions the
advanced-stats rules require, so a slick-but-unsound NMA is caught.

Input: a structured NMA spec (JSON), e.g.
    {
      "treatments": ["A", "B", "C"],
      "comparisons": [{"t1": "A", "t2": "B", "k": 5, "I2": 30, "tau2": 0.02}, ...],
      "consistency": {"method": "design-by-treatment", "p": 0.41},   # or null
      "sucra": {"A": 0.82, "B": 0.55, "C": 0.13},                    # or null
      "ranking_uncertainty_reported": true
    }

Checks (advanced-stats.md NMA section):
  - network connected: single component, every treatment appears (no isolated node)
  - >= 3 treatments (else it's a pairwise MA, not a network)
  - consistency assessed (design-by-treatment / node-split reported)
  - consistency not violated (reported p >= 0.05; flag p < 0.05)
  - single-study comparisons (k == 1) — fragile direct evidence
  - high heterogeneity (I2 > 75) — common-τ² assumption strained
  - SUCRA reported without ranking uncertainty (rankogram/CrI) — ranking misuse

Stdlib only, deterministic, offline.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


def _connected(treatments: list[str], edges: list[tuple[str, str]]) -> tuple[bool, list[str]]:
    """Return (is_single_component_covering_all, isolated_or_extra_treatments)."""
    adj: dict[str, set[str]] = defaultdict(set)
    nodes_in_edges: set[str] = set()
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
        nodes_in_edges.update((a, b))
    isolated = [t for t in treatments if t not in nodes_in_edges]
    if not treatments:
        return False, isolated
    # BFS from the first treatment that appears in an edge (or first treatment)
    start = next((t for t in treatments if t in nodes_in_edges), treatments[0])
    seen = {start}
    stack = [start]
    while stack:
        cur = stack.pop()
        for nb in adj[cur]:
            if nb not in seen:
                seen.add(nb)
                stack.append(nb)
    all_covered = set(treatments) <= seen
    return (all_covered and not isolated), isolated


def check_nma(spec: dict) -> dict:
    treatments = [str(t) for t in spec.get("treatments", [])]
    comparisons = spec.get("comparisons", []) or []
    edges = [(str(c.get("t1")), str(c.get("t2"))) for c in comparisons
             if c.get("t1") and c.get("t2")]

    findings: list[dict] = []

    def flag(check, severity, detail):
        findings.append({"check": check, "severity": severity, "detail": detail})

    if len(treatments) < 3:
        flag("min_treatments", "error",
             f"{len(treatments)} treatments — an NMA needs >=3 (else use pairwise MA)")

    connected, isolated = _connected(treatments, edges)
    if not connected:
        flag("network_connected", "error",
             f"network is not a single connected component"
             + (f"; isolated treatments: {isolated}" if isolated else ""))

    consistency = spec.get("consistency")
    if not consistency:
        flag("consistency_assessed", "warn",
             "no global inconsistency assessment (design-by-treatment / node-split) reported")
    else:
        p = consistency.get("p")
        if isinstance(p, (int, float)) and p < 0.05:
            flag("consistency_violated", "error",
                 f"inconsistency detected (p={p}) — consistency assumption questionable")

    single = [f"{c.get('t1')}-{c.get('t2')}" for c in comparisons if c.get("k") == 1]
    if single:
        flag("single_study_comparisons", "warn",
             f"{len(single)} direct comparison(s) informed by a single study: {single[:5]}")

    hi_het = [f"{c.get('t1')}-{c.get('t2')}" for c in comparisons
              if isinstance(c.get("I2"), (int, float)) and c["I2"] > 75]
    if hi_het:
        flag("high_heterogeneity", "warn",
             f"{len(hi_het)} comparison(s) with I²>75% — common-τ² assumption strained: {hi_het[:5]}")

    if spec.get("sucra") and not spec.get("ranking_uncertainty_reported"):
        flag("sucra_without_uncertainty", "warn",
             "SUCRA/P-score rankings reported without ranking uncertainty (rankogram/CrI) — "
             "treatment-ranking over-interpretation risk")

    errors = sum(1 for f in findings if f["severity"] == "error")
    warns = sum(1 for f in findings if f["severity"] == "warn")
    return {
        "treatments": len(treatments),
        "comparisons": len(comparisons),
        "status": "fail" if errors else ("warn" if warns else "ok"),
        "errors": errors,
        "warnings": warns,
        "findings": findings,
    }


def check_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {"error": f"not found: {p}"}
    try:
        spec = json.loads(p.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        return {"error": f"invalid JSON: {e}"}
    result = check_nma(spec)
    result["source"] = str(p)
    return result
