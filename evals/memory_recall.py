"""Eval 3 — LongMemEval-style memory recall/precision probe (compact).

Seeds a real ``MemoryStore`` (SQLite + FTS5) with facts including
superseded/temporal ones, then queries it and measures whether recall returns
the CURRENT fact and SUPPRESSES superseded / expired ones.

This is the change-over-time capability that LongMemEval and Zep/Graphiti target
(SYSTEMS-BENCHMARK §3): our store has temporal validity (`valid_until`,
`supersede`, `expire_memories`) but had never been benchmarked. This probe puts a
number on it.

Metrics (over the supersession probes):
  * ``recall``                  — fraction of probes whose CURRENT fact is in top-k.
  * ``precision``               — current-fact hits / total returned items
                                  (a returned superseded fact lowers precision).
  * ``stale_suppression_rate``  — fraction of probes returning NO superseded fact.
Plus an expired-fact probe (valid_until in the past): the fact must be absent.

Deterministic: fixed fixtures, fixed IDs, no randomness; superseded facts get
``status=expired`` + a past ``valid_until`` and are filtered by the store's own
active+temporal query, so results are reproducible.
"""
from __future__ import annotations

from dataclasses import dataclass

from overmind.memory.store import MemoryStore
from overmind.storage.db import StateDatabase
from overmind.storage.models import MemoryRecord

from evals.common import pct, write_result

_PAST = "2020-01-01T00:00:00+00:00"


@dataclass(frozen=True)
class SupersessionProbe:
    topic: str
    query: str
    old_id: str
    old_title: str
    old_content: str
    new_id: str
    new_title: str
    new_content: str


# Four facts that changed over time. The OLD value is superseded by the NEW one;
# a correct recall returns NEW and never surfaces OLD.
_PROBES: list[SupersessionProbe] = [
    SupersessionProbe(
        "pairwisepro_runtime", "PairwisePro suite runtime seconds",
        "mem_pp_old", "PairwisePro suite runtime", "PairwisePro full test suite runs in 30 seconds.",
        "mem_pp_new", "PairwisePro suite runtime", "PairwisePro full test suite runs in 12 seconds.",
    ),
    SupersessionProbe(
        "deploy_target", "MetaAudit deploy target",
        "mem_dt_old", "MetaAudit deploy target", "MetaAudit deploys to Heroku.",
        "mem_dt_new", "MetaAudit deploy target", "MetaAudit deploys to Fly.io.",
    ),
    SupersessionProbe(
        "portfolio_count", "portfolio project count",
        "mem_pc_old", "Portfolio project count", "The portfolio contains 465 projects.",
        "mem_pc_new", "Portfolio project count", "The portfolio contains 472 projects.",
    ),
    SupersessionProbe(
        "certbundle_signer", "CertBundle default signer",
        "mem_cs_old", "CertBundle default signer", "CertBundle signs with HMAC by default.",
        "mem_cs_new", "CertBundle default signer", "CertBundle signs with Ed25519 by default.",
    ),
]

# Stable distractor facts (never superseded) so recall is non-trivial — the store
# holds plenty of other content the query must rank below the right answer.
_DISTRACTORS: list[tuple[str, str, str]] = [
    ("mem_d1", "Sentinel rule count", "Sentinel ships 57 rules across YAML and Python plugins."),
    ("mem_d2", "Judge engine default", "OVERMIND_JUDGE_ENGINE defaults to the claude,gemini chain."),
    ("mem_d3", "Memory decay rate", "Feedback memories decay at 0.99 relevance per tick."),
    ("mem_d4", "Numerical baseline policy", "A missing numerical baseline yields UNVERIFIED, never CERTIFIED."),
]

# Expired temporal fact (valid_until in the past, no replacement). Must be
# suppressed after expire_old().
_EXPIRED = ("mem_exp", "Nightly token budget", "Nightly verify token budget is 50000 tokens.",
            "nightly token budget")


def _mk(mid: str, title: str, content: str, valid_until: str | None = None) -> MemoryRecord:
    return MemoryRecord(
        memory_id=mid, memory_type="project_learning", scope="portfolio",
        title=title, content=content, valid_until=valid_until,
    )


def _seed(store: MemoryStore) -> None:
    # Supersession pairs: save OLD, then supersede with NEW.
    for p in _PROBES:
        store.save(_mk(p.old_id, p.old_title, p.old_content))
        store.supersede(p.old_id, _mk(p.new_id, p.new_title, p.new_content))
    for mid, title, content in _DISTRACTORS:
        store.save(_mk(mid, title, content))
    # Expired fact + flip it to expired status.
    store.save(_mk(_EXPIRED[0], _EXPIRED[1], _EXPIRED[2], valid_until=_PAST))
    store.expire_old()


def evaluate() -> dict:
    workdir = _tmp_dir("db")
    db = StateDatabase(workdir / "memory.db")
    try:
        store = MemoryStore(db=db, checkpoints_dir=workdir / "cp", logs_dir=workdir / "logs")
        _seed(store)

        probe_rows = []
        total_returned = 0
        total_current_hits = 0
        recall_hits = 0
        stale_suppressed = 0
        naive_stale_leaks = 0  # counterfactual: would a no-temporal-filter search leak?
        for p in _PROBES:
            results = store.search(p.query, limit=5)
            ids = [m.memory_id for m in results]
            current_in = p.new_id in ids
            stale_in = p.old_id in ids
            naive_ids = _naive_fts_ids(db, p.query, limit=5)
            naive_stale_leaks += int(p.old_id in naive_ids)
            total_returned += len(ids)
            total_current_hits += sum(1 for i in ids if i == p.new_id)
            recall_hits += int(current_in)
            stale_suppressed += int(not stale_in)
            probe_rows.append({
                "topic": p.topic, "query": p.query,
                "returned_ids": ids,
                "current_recalled": current_in,
                "stale_leaked": stale_in,
                "top1_is_current": bool(ids) and ids[0] == p.new_id,
                "naive_would_leak_stale": p.old_id in naive_ids,
            })

        n = len(_PROBES)
        recall = pct(recall_hits, n)
        precision = pct(total_current_hits, total_returned)
        stale_suppression_rate = pct(stale_suppressed, n)
        top1 = pct(sum(1 for r in probe_rows if r["top1_is_current"]), n)
        naive_stale_leak_rate = pct(naive_stale_leaks, n)

        # Expired probe: the fact must NOT come back.
        exp_results = store.search(_EXPIRED[3], limit=5)
        exp_ids = [m.memory_id for m in exp_results]
        expired_suppressed = _EXPIRED[0] not in exp_ids

        payload = {
            "eval": "memory_recall",
            "n_supersession_probes": n,
            "recall": recall,
            "precision": precision,
            "stale_suppression_rate": stale_suppression_rate,
            "top1_is_current_rate": top1,
            "naive_stale_leak_rate": naive_stale_leak_rate,
            "naive_baseline_note": (
                "naive_stale_leak_rate = fraction of probes where an FTS search "
                "WITHOUT the active+temporal filter returns the superseded fact. "
                "Superseded facts share title/keywords with the current one, so a "
                "high naive leak vs a low real stale-leak shows the temporal filter "
                "(not keyword mismatch) is doing the suppression."
            ),
            "expired_probe": {
                "query": _EXPIRED[3],
                "returned_ids": exp_ids,
                "expired_fact_suppressed": expired_suppressed,
            },
            "probes": probe_rows,
        }
        return payload
    finally:
        db.close()


def _naive_fts_ids(db: StateDatabase, query: str, limit: int = 5) -> list[str]:
    """Counterfactual recall: same FTS match, but WITHOUT the active+temporal
    filter that ``search_memories`` applies. Shows what a store lacking temporal
    validity would surface (i.e. whether superseded facts would leak)."""
    fts_operators = {"AND", "OR", "NOT", "NEAR"}
    tokens = [t for t in query.split() if t and t.upper() not in fts_operators]
    fts_query = " ".join(f'"{t}"' for t in tokens)
    if not fts_query:
        return []
    rows = db.connection.execute(
        "SELECT m.id FROM memories m JOIN memories_fts f ON m.rowid = f.rowid "
        "WHERE memories_fts MATCH ? ORDER BY rank LIMIT ?",
        (fts_query, limit),
    ).fetchall()
    return [r["id"] for r in rows]


# Local import kept lazy/simple to avoid a hard tempfile dep at module import.
def _tmp_dir(suffix: str):
    import tempfile
    from pathlib import Path
    return Path(tempfile.mkdtemp(prefix=f"memrecall_{suffix}_"))


def main() -> dict:
    payload = evaluate()
    path = write_result("memory_recall", payload)
    print(f"[memory_recall] recall={payload['recall']:.2%} precision={payload['precision']:.2%} "
          f"stale_suppression={payload['stale_suppression_rate']:.2%} "
          f"top1_current={payload['top1_is_current_rate']:.2%}")
    print(f"[memory_recall] counterfactual naive_stale_leak_rate="
          f"{payload['naive_stale_leak_rate']:.2%} (vs our stale leak "
          f"{1 - payload['stale_suppression_rate']:.2%}) -- temporal filter is the defense")
    print(f"[memory_recall] expired-fact suppressed: "
          f"{payload['expired_probe']['expired_fact_suppressed']}")
    print(f"[memory_recall] -> {path}")
    return payload


if __name__ == "__main__":
    main()
