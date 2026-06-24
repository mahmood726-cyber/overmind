"""Eval 7 — claim→evidence retraction propagation (audit B2).

When a source-grounded fact goes stale (its source file changed), the *flat*
freshness model (`MemoryStore.invalidate_stale`) expires only that one fact — a
conclusion DERIVED FROM it is left standing. *Grounded Continuation*
(arXiv:2605.14175) prescribes the fix: propagate the retraction through the
claim→evidence graph so every transitive dependent is invalidated too. This eval
puts a number on the difference.

Setup (real `MemoryStore`, SQLite): a source-grounded premise **A** (hashed to a
temp file), **B** `derived_from` A, **C** `derived_from` B, and an independent
**D**. Then the source file is mutated so A is stale.

When A's source changes, the facts that SHOULD be invalidated are {A, B, C}
(A directly + everything derived from it). D must stay.

Headline — **transitive-invalidation recall** = caught / should-be-caught:

  flat `invalidate_stale`          →  catches {A}        (1/3)
  graph `..._with_propagation`     →  catches {A, B, C}  (3/3)

with **D never invalidated** in either (no over-propagation).
"""
from __future__ import annotations

import hashlib

from overmind.memory.store import MemoryStore
from overmind.storage.db import StateDatabase
from overmind.storage.models import MemoryRecord

from evals.common import pct, write_result


def _tmp_dir(suffix: str):
    import tempfile
    from pathlib import Path
    return Path(tempfile.mkdtemp(prefix=f"memretract_{suffix}_"))


def _seed(store: MemoryStore, source_path):
    """A (source-grounded) <- B <- C ; D independent."""
    src_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()[:16]
    a = MemoryRecord(
        memory_id="A", memory_type="project_learning", scope="portfolio",
        title="premise A", content="A: derived from a source file.",
        source_path=str(source_path), source_hash=src_hash,
    )
    b = MemoryRecord(
        memory_id="B", memory_type="project_learning", scope="portfolio",
        title="claim B", content="B: concluded from A.", derived_from=["A"],
    )
    c = MemoryRecord(
        memory_id="C", memory_type="project_learning", scope="portfolio",
        title="claim C", content="C: concluded from B.", derived_from=["B"],
    )
    d = MemoryRecord(
        memory_id="D", memory_type="project_learning", scope="portfolio",
        title="independent D", content="D: unrelated, depends on nothing.",
    )
    store.save_batch([a, b, c, d])


def _active_ids(store: MemoryStore) -> set[str]:
    return {m.memory_id for m in store.list_all(status="active", limit=1000)}


def _run(propagate: bool) -> dict:
    workdir = _tmp_dir("flat" if not propagate else "graph")
    src = workdir / "source.txt"
    src.write_text("original source content\n", encoding="utf-8")
    db = StateDatabase(workdir / "mem.db")
    try:
        store = MemoryStore(db=db, checkpoints_dir=workdir / "cp", logs_dir=workdir / "logs")
        _seed(store, src)
        # Mutate the source so A is now stale.
        src.write_text("CHANGED source content\n", encoding="utf-8")
        before = _active_ids(store)
        if propagate:
            store.invalidate_stale_with_propagation()
        else:
            store.invalidate_stale()
        after = _active_ids(store)
        invalidated = sorted(before - after)
        return {"invalidated": invalidated, "still_active": sorted(after)}
    finally:
        db.close()


def evaluate() -> dict:
    should_invalidate = {"A", "B", "C"}   # A stale + everything derived from it
    must_keep = "D"

    flat = _run(propagate=False)
    graph = _run(propagate=True)

    flat_caught = should_invalidate & set(flat["invalidated"])
    graph_caught = should_invalidate & set(graph["invalidated"])

    payload = {
        "eval": "memory_retraction",
        "should_invalidate": sorted(should_invalidate),
        "flat": {
            "invalidated": flat["invalidated"],
            "transitive_recall": pct(len(flat_caught), len(should_invalidate)),
            "over_propagated_D": must_keep in flat["invalidated"],
        },
        "graph": {
            "invalidated": graph["invalidated"],
            "transitive_recall": pct(len(graph_caught), len(should_invalidate)),
            "over_propagated_D": must_keep in graph["invalidated"],
        },
        "improvement": {
            "transitive_recall_before": pct(len(flat_caught), len(should_invalidate)),
            "transitive_recall_after": pct(len(graph_caught), len(should_invalidate)),
            "D_preserved_both": (must_keep not in flat["invalidated"]
                                 and must_keep not in graph["invalidated"]),
        },
    }
    return payload


def main() -> dict:
    payload = evaluate()
    imp = payload["improvement"]
    path = write_result("memory_retraction", payload)
    print(f"[memory_retraction] transitive-invalidation recall: "
          f"{imp['transitive_recall_before']:.0%} (flat) -> "
          f"{imp['transitive_recall_after']:.0%} (graph)  "
          f"[flat={payload['flat']['invalidated']} graph={payload['graph']['invalidated']}]")
    print(f"[memory_retraction] independent D preserved in both: {imp['D_preserved_both']} "
          f"(no over-propagation)")
    print(f"[memory_retraction] -> {path}")
    return payload


if __name__ == "__main__":
    main()
