"""Ecosystem quality scorecard (1E) — the local "measuring stick".

Offline, deterministic, orchestrator-free. Quantifies the quality of the
context/memory layer so later changes can be compared against a baseline
(record a scorecard before a change; re-run after).

Suites:
  - **memory recall**: self-recall — use each memory doc's own `description` as
    a query and check it ranks #1 (and within top-k) among all docs via the
    BM25 index. Measures index discriminability without hardcoding any personal
    queries into this (public) repo. recall@1 / recall@k / MRR.
  - **context integrity**: every ref in `rules/_index.yaml` (always + each
    rule's load + fallback) must resolve to a real file + section.

Sentinel rule-precision and Overmind verdict-reliability are intentionally NOT
re-implemented here — those are already measured by Sentinel's own pytest
regression corpus and `overmind meta-verify`. This scorecard references them
rather than duplicating.
"""
from __future__ import annotations

from pathlib import Path

from overmind.memory import file_index as fi
from overmind.context import rules_index as ri


def eval_memory_recall(roots: list[Path] | None = None, k: int = 3) -> dict:
    docs = fi.load_docs(roots)
    n = len(docs)
    if n < 2:
        return {"n_docs": n, "note": "need >=2 docs for a recall eval", "recall@1": None}
    hits1 = hitsk = 0
    rr_sum = 0.0
    per_doc = []
    for target in docs:
        query = target.description or target.slug
        ranked = fi.bm25_recall(docs, query, k=n)
        order = [d.slug for d, _ in ranked]
        rank = order.index(target.slug) + 1 if target.slug in order else 0
        if rank == 1:
            hits1 += 1
        if rank and rank <= k:
            hitsk += 1
        if rank:
            rr_sum += 1.0 / rank
        per_doc.append({"slug": target.slug, "rank": rank})
    return {
        "n_docs": n,
        "recall@1": round(hits1 / n, 3),
        f"recall@{k}": round(hitsk / n, 3),
        "mrr": round(rr_sum / n, 3),
        "per_doc": per_doc,
    }


def eval_context_integrity(rules_dir: Path | None = None) -> dict:
    rules_dir = rules_dir or ri.default_rules_dir()
    index = ri.load_index(rules_dir)
    if not index:
        return {"present": False}
    refs: list[str] = list(index.get("always", []) or [])
    for entry in index.get("rules", []) or []:
        refs += entry.get("load", []) or []
    refs += index.get("fallback", []) or []
    seen: list[str] = []
    for r in refs:
        if r not in seen:
            seen.append(r)
    unresolved = [r for r in seen if not ri.resolve_ref(r, rules_dir)["found"]]
    return {
        "present": True,
        "total_refs": len(seen),
        "resolved": len(seen) - len(unresolved),
        "unresolved": unresolved,
        "integrity": "ok" if not unresolved else "drift",
    }


def run(k: int = 3) -> dict:
    mem = eval_memory_recall(k=k)
    ctx = eval_context_integrity()
    consolidate = fi.cmd_consolidate()

    status = "ok"
    if ctx.get("present") and ctx.get("integrity") == "drift":
        status = "context-drift"
    r1 = mem.get("recall@1")
    if r1 is not None and r1 < 0.5:
        status = "memory-weak"

    return {
        "status": status,
        "scorecard": {
            "memory": {
                "recall@1": mem.get("recall@1"),
                f"recall@{k}": mem.get(f"recall@{k}"),
                "mrr": mem.get("mrr"),
                "n_docs": mem.get("n_docs"),
                "undated_facts": len(consolidate.get("undated_no_review_field", [])),
                "near_duplicates": len(consolidate.get("near_duplicates", [])),
                "orphan_links": len(consolidate.get("orphan_links", [])),
            },
            "context": ctx,
        },
        "external_measures": {
            "sentinel_rule_precision": "Sentinel pytest regression corpus (run `pytest` in the Sentinel repo)",
            "overmind_verdict_reliability": "`overmind meta-verify`",
            "portfolio_findings": "`overmind aggregate-findings`",
        },
        "detail": {"memory_recall": mem},
    }
