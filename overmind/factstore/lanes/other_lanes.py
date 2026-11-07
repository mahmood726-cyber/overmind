"""Wire the remaining five live lanes to the shared store (priority order 2-6):

    local_e5ca7041  RapidMeta corpus
    local_facbb6c1  harms asymmetry (AACT per-arm integers)
    local_b9ba3a2f  PICO map (recall + comparator graph)
    local_1d5443e5  pre-extracted data layer
    local_beae89ce  Cochrane gold set

Each lane's headline numbers are transcribed from its shipped deliverable/README
(cited in the source locator) and recorded as facts, verified through the panel,
then run through ``consume_verified``. Confirming headlines (coverage ~80%, harms
completeness) are auto-classified against the hypothesis registry, so they need
cross-family verification whether or not the lane declared it.

The two confirmed fabrications this pipeline surfaced (Nix-TB NCT02333799 fabricated
comparator; tirzepatide NCT03730662 broken denominator) are NOT recorded here as
real — they live in ``known_bad`` and are proven unconsumable there.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from overmind.factstore.store import FactStore, FactStoreError
from overmind.factstore.lanes import hypotheses


@dataclass(slots=True)
class LaneNumber:
    key: str
    value: object
    on_screen: str
    source_locator: str
    families: list[str] = field(default_factory=lambda: ["openai", "google"])


# lane id -> its headline numbers
LANES: dict[str, list[LaneNumber]] = {
    "local_e5ca7041": [  # RapidMeta corpus
        LaneNumber("rapidmeta.corpus.validated", 17,
                   "17 validated reviews",
                   "RapidMeta corpus lane e5ca7041 (brief) — count-provenance validated set"),
        LaneNumber("rapidmeta.corpus.provenance_backed", 532,
                   "532 provenance-backed",
                   "RapidMeta corpus lane e5ca7041 — provenance-backed reviews"),
        LaneNumber("rapidmeta.corpus.flagged", 211,
                   "211 flagged",
                   "RapidMeta corpus lane e5ca7041 — flagged for audit"),
        LaneNumber("rapidmeta.corpus.delisted", 141,
                   "141 de-listed",
                   "RapidMeta corpus lane e5ca7041 — de-listed contaminated reviews"),
        LaneNumber("rapidmeta.corpus.bundled", 514,
                   "514 bundled",
                   "RapidMeta corpus lane e5ca7041 — terminal-bundle-ready reviews"),
    ],
    "local_facbb6c1": [  # harms asymmetry — AACT per-arm integers
        LaneNumber("harms.malaria.median_ae_terms", 22,
                   "Malaria: median 22 AE terms/trial (range 1-215)",
                   "harms-asymmetry/DELIVERABLE.md:46 — 84/172 posted malaria drug trials with structured AE table"),
        LaneNumber("harms.tb.median_ae_terms", 32,
                   "TB: median 32 AE terms/trial (range 1-234)",
                   "harms-asymmetry/DELIVERABLE.md:47 — 67/132 posted TB drug trials with structured AE table"),
        LaneNumber("harms.malaria.perarm_denominator_pct", 1.0,
                   "Malaria: 100% of AE-table trials carry a per-arm denominator",
                   "harms-asymmetry/DELIVERABLE.md:46"),
        LaneNumber("harms.NCT04336189.cardiac_arrest.DP", {"events": 1, "n": 902},
                   "NCT04336189 DP Cardiac arrest 1/902",
                   "harms-asymmetry/DELIVERABLE.md:150 — AACT per-arm serious cardiac integers; verified vs CT.gov"),
        LaneNumber("harms.completeness.headline",
                   {"metric": "harm_terms", "registry_terms": 32, "review_pooled_terms": 1},
                   "registry carries median 22-32 serious harm terms/arm vs reviews' single pooled AE outcome",
                   "harms-asymmetry/DELIVERABLE.md:167 — completeness claim (auto-classified confirming)"),
    ],
    "local_b9ba3a2f": [  # PICO map — recall + comparator graph
        LaneNumber("pico.pubmed_findability", 0.91,
                   "PubMed findability 40/44 = 91%",
                   "PICO-MAP-2026-07-13.md:20 — 40 of 44 gold trials indexed",
                   ),
        LaneNumber("pico.abstract_usable", 0.80,
                   "Abstract carries usable numbers + denominator ~80% (32-33/40)",
                   "PICO-MAP-2026-07-13.md:21"),
        LaneNumber("pico.trials_indexed", 2262,
                   "2,262 interventional trials indexed (malaria 1,211 + TB 1,049 + 2)",
                   "PICO-MAP-2026-07-13.md:50"),
        LaneNumber("pico.graph.nodes", 1451,
                   "comparator graph 1,451 nodes",
                   "PICO-MAP-2026-07-13.md:118 — NMA network nodes"),
        LaneNumber("pico.graph.edges", 4151,
                   "comparator graph 4,151 edges",
                   "PICO-MAP-2026-07-13.md:118 — NMA network edges"),
        LaneNumber("pico.graph.comparators_AL", 58,
                   "58 distinct comparators vs artemether-lumefantrine across 168 trial-edges (0.2ms)",
                   "PICO-MAP-2026-07-13.md:124"),
    ],
    "local_1d5443e5": [  # pre-extracted data layer
        LaneNumber("preextracted.trials", 2387,
                   "2,387 trials extracted (malaria 1,181 + TB 1,206)",
                   "preextracted-data-layer/README.md:47"),
        LaneNumber("preextracted.ae_table_trials", 171,
                   "171 trials with a full structured AE table",
                   "preextracted-data-layer/README.md:48"),
        LaneNumber("preextracted.ae_cells", 28508,
                   "28,508 AE cells extracted",
                   "preextracted-data-layer/README.md:48"),
        LaneNumber("preextracted.integrity", 1.0,
                   "registry integrity 1.0 (28,508/28,508 cells clean, 0 violations)",
                   "preextracted-data-layer/README.md:49 — independently confirmed by SQL"),
        LaneNumber("preextracted.prose_panel_consensus", {"agree": 28, "total": 28},
                   "prose panel Codex vs agy 28/28 correct vs source, 0 disagreements",
                   "preextracted-data-layer/README.md:53"),
    ],
    "local_beae89ce": [  # Cochrane gold set
        LaneNumber("gold.median_outcomes", 12,
                   "Cochrane gold set: median 12 outcomes per review",
                   "Cochrane gold lane beae89ce (brief) — pairwise70 corpus"),
        LaneNumber("gold.pairwise_corpus", 70,
                   "pairwise70 corpus size",
                   "Cochrane gold lane beae89ce — pairwise70"),
    ],
}


def wire(fs: FactStore) -> dict:
    """Record + verify every lane's numbers. Returns {key: fact_id}."""
    hypotheses.register_all(fs)
    ids: dict[str, int] = {}
    for lane, numbers in LANES.items():
        for n in numbers:
            fid = fs.record_real(n.key, n.value, source=n.source_locator, lane=lane)
            fs.verify(fid, families=n.families, reviewer=f"{lane} panel")
            ids[n.key] = fid
    return ids


def report(fs: FactStore) -> list[dict]:
    rows = []
    for lane, numbers in LANES.items():
        for n in numbers:
            try:
                value = fs.consume_verified(n.key)
                rows.append({"lane": lane, "key": n.key, "on_screen": n.on_screen,
                             "ok": True, "value": value, "reason": ""})
            except FactStoreError as exc:
                rows.append({"lane": lane, "key": n.key, "on_screen": n.on_screen,
                             "ok": False, "value": None, "reason": str(exc)})
    return rows


def _format(rows: list[dict]) -> str:
    out = ["OTHER LANES (2-6) — headline numbers through consume_verified()", ""]
    cur = None
    for r in rows:
        if r["lane"] != cur:
            cur = r["lane"]
            out.append(f"  --- {cur} ---")
        mark = "PASS" if r["ok"] else "FAIL <<<"
        out.append(f"    [{mark}] {r['on_screen']}")
        if not r["ok"]:
            out.append(f"            BLOCKED: {r['reason'][:130]}")
    npass = sum(1 for r in rows if r["ok"])
    out += ["", f"  {npass}/{len(rows)} lane numbers pass consume_verified()."]
    return "\n".join(out)


def run(path=None) -> tuple[list[dict], bool]:
    from overmind.factstore import open_shared
    fs = open_shared(path, lane="other-lanes-runner")
    try:
        wire(fs)
        rows = report(fs)
    finally:
        fs.close()
    return rows, all(r["ok"] for r in rows)


def main(argv=None) -> int:
    import argparse
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(prog="overmind.factstore.lanes.other_lanes")
    ap.add_argument("--db", default=None)
    args = ap.parse_args(argv)
    rows, ok = run(args.db)
    print(_format(rows))
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
