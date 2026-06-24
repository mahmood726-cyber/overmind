"""Eval 10 — cross-repo contract-impact fan-out (audit B1).

When a SHARED module/schema changes, which dependent repos must re-run their
witnesses? A per-repo verifier that only re-checks *direct* consumers misses
**dependents-of-dependents** — and the house lesson (and the C5 delta-skip
caveat) is explicit: never skip a repo whose upstream dependency changed.

Setup (`ContractImpactGraph`, reusing the ClaimGraph transitive closure):
shared module **M**; **A** and **C** depend on M; **B** depends on A (so B
transitively depends on M); **D** is independent. M changes.

  should re-verify = {A, B, C}   (A, C direct; B transitive)   D stays.

Headline — **impact recall** (impacted repos correctly selected):

  naive direct-only   →   67 % (catches {A, C}, MISSES B)
  graph closure       →  100 % (catches {A, B, C})

with **D never selected** (no over-fan-out). A miss here is the dangerous case
(a broken dependent ships unverified), so 100% recall is the safety bar.
"""
from __future__ import annotations

from overmind.verification.contract_impact import ContractImpactGraph

from evals.common import pct, write_result


def _portfolio() -> ContractImpactGraph:
    g = ContractImpactGraph()
    g.add_repo("D")                       # independent
    g.add_dependency("A", depends_on="M")  # A consumes shared module M
    g.add_dependency("C", depends_on="M")  # C consumes M
    g.add_dependency("B", depends_on="A")  # B depends on A (transitive on M)
    return g


def evaluate() -> dict:
    g = _portfolio()
    should_impact = {"A", "B", "C"}
    must_not_select = "D"

    graph_impacted = set(g.impacted_by("M").impacted_repos)
    naive_impacted = set(g.naive_impacted_by("M"))

    graph_recall = pct(len(should_impact & graph_impacted), len(should_impact))
    naive_recall = pct(len(should_impact & naive_impacted), len(should_impact))

    payload = {
        "eval": "contract_impact",
        "changed_module": "M",
        "should_impact": sorted(should_impact),
        "naive_impacted": sorted(naive_impacted),
        "graph_impacted": sorted(graph_impacted),
        "impact_recall_before": naive_recall,    # naive direct-only
        "impact_recall_after": graph_recall,     # graph transitive closure
        "missed_by_naive": sorted(should_impact - naive_impacted),
        "missed_by_graph": sorted(should_impact - graph_impacted),
        "independent_not_selected": must_not_select not in graph_impacted,
        "no_dependent_skipped": should_impact <= graph_impacted,
    }
    return payload


def main() -> dict:
    payload = evaluate()
    path = write_result("contract_impact", payload)
    print(f"[contract_impact] impact recall: {payload['impact_recall_before']:.0%} (naive direct-only) "
          f"-> {payload['impact_recall_after']:.0%} (graph closure)")
    print(f"[contract_impact] missed by naive: {payload['missed_by_naive']}; "
          f"no dependent skipped by graph: {payload['no_dependent_skipped']}; "
          f"independent D not selected: {payload['independent_not_selected']}")
    print(f"[contract_impact] -> {path}")
    return payload


if __name__ == "__main__":
    main()
