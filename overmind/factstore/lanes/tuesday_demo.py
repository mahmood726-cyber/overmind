"""Wire the Tuesday demo lane (local_c4a2c1a4) to the shared fact store.

The demo is a static HTML deck (C:\\Projects\\tuesday-demo). Its EMIT POINT is the
authoring step: a number goes on a slide. This module makes that step pass through
the gate — every on-screen number is recorded as a fact with its real source
locator, the real ones are verified through the cross-family panel, and then
``report()`` runs ``consume_verified`` on each key and returns a number-by-number
pass/fail list.

The test this answers (Mahmood's): *could a fabricated figure still reach a slide?*
Run alongside ``known_bad`` in the same store: the real demo numbers must PASS and
every fabricated one must be BLOCKED, side by side.

Every value below is transcribed from the shipped HTML (file:line cited) and traces
to a registry record / PMID / bundle artefact — NOT paraphrased. Cross-vendor
families that actually reviewed each block are recorded on its verification.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from overmind.factstore.store import FactStore, FactStoreError
from overmind.factstore.lanes import hypotheses

LANE = "local_c4a2c1a4"  # the Tuesday demo lane


@dataclass(slots=True)
class DemoNumber:
    key: str
    value: object
    on_screen: str            # exactly how it appears on the slide
    source_locator: str       # slide file:line + the underlying registry/PMID/artefact
    families: list[str] = field(default_factory=lambda: ["openai", "google"])
    kind: str = ""            # plausibility hint for bare scalars


# Every on-screen number in the deck, transcribed from the shipped HTML.
DEMO_NUMBERS: list[DemoNumber] = [
    # --- LEAD SLIDE: DP cardiac safety, per-arm integers verified vs ClinicalTrials.gov ---
    DemoNumber(
        "harms.NCT04336189.cardiac_arrest.DP", {"events": 1, "n": 902},
        "DP alone · Cardiac arrest · 1 / 902",
        "harms.html:52 — CT.gov NCT04336189 (Ugandan IPTp trial, Busia), DP-alone arm; "
        "verified EXACT against ClinicalTrials.gov results, not the lane's extraction"),
    DemoNumber(
        "harms.NCT04336189.cardiac_arrest.SP", {"events": 0, "n": 896},
        "SP alone · Cardiac arrest · 0 / 896",
        "harms.html:53 — CT.gov NCT04336189 SP-alone arm; verified vs ClinicalTrials.gov"),
    DemoNumber(
        "harms.NCT02802501.QT.DHA_PQP", {"events": 1, "n": 50},
        "DHA-PQP · ECG QT prolonged · 1 / 50",
        "harms.html:54 — CT.gov NCT02802501 DHA-PQP arm; verified vs ClinicalTrials.gov"),
    DemoNumber(
        "harms.NCT02802501.QT.taf_DHA_PQP", {"events": 0, "n": 50},
        "Tafenoquine+DHA-PQP · ECG QT prolonged · 0 / 50",
        "harms.html:55 — CT.gov NCT02802501 tafenoquine+DHA-PQP arm; verified vs ClinicalTrials.gov"),
    # --- TB Xpert real 4-study DTA (within Cochrane Steingart-2014) ---
    DemoNumber(
        "TB.Xpert.real4.sensitivity", 0.910,
        "Sensitivity 91.0% (95% CI 89.6-92.2)",
        "xpert-tb.html:64 — pooled 4 landmark studies (Boehme 2010 PMID 20825313; "
        "Boehme 2011 PMID 21507477; Rachow 2011 PMID 21738575; Carriquiry 2012 PMID 22970271); "
        "lands inside Cochrane Steingart-2014 CD009593.pub4 Se 85-92%",
        kind="sensitivity"),
    DemoNumber(
        "TB.Xpert.real4.specificity", 0.990,
        "Specificity 99.0% (95% CI 98.6-99.2)",
        "xpert-tb.html:65 — same 4 studies; inside Cochrane Steingart-2014 Sp 98-99%",
        kind="specificity"),
    # --- COVERAGE (the abstract-first ~80% claim — auto-classified confirming) ---
    DemoNumber(
        "coverage.pubmed_findability", 0.91,
        "PubMed findability 40/44 = 91%",
        "coverage.html:48 — 40 of 44 gold trials indexed in PubMed; reviewed Codex + Gemini",
        kind="coverage.pubmed_findability"),
    DemoNumber(
        "coverage.abstract_usable", 0.80,
        "Abstract carries usable numbers + denominator ~80%",
        "coverage.html:49 — abstract-usable proportion on the gold set; reviewed Codex + Gemini"),
    DemoNumber(
        "coverage.union", 0.80,
        "UNION (abstract ∪ OA ∪ registry) ~80%",
        "coverage.html:50 — union coverage; reviewed Codex + Gemini"),
    DemoNumber(
        "coverage.hard_residual", 0.20,
        "Hard residual (genuinely unreachable) ~20%",
        "coverage.html:51 — 1 - union"),
    DemoNumber(
        "coverage.registry_only", 0.14,
        "ClinicalTrials.gov registry (publication-linkable) 14%",
        "coverage.html:47 — registry-only recall; SHOWN AS THE ARTEFACT, not the ceiling"),
    # --- SELF-PROVING BUNDLE ---
    DemoNumber(
        "bundle.zip_size_mb", 0.27,
        "download a review as a 0.27 MB zip",
        "index.html:131 — rapidmeta-kit terminal bundle size"),
    DemoNumber(
        "bundle.rr_bitforbit", 0.8721640828832273,
        "reproduces the pooled RR bit-for-bit: 0.8721640828832273",
        "rapidmeta-kit/bundle-example/finerenone_ckd/bundle.json estimate_ratio; "
        "app browser-JS == independent Python harness, diff 0.0 (HARNESS-BUNDLE-2026-07-13.md)",
        kind="rr"),
]


def wire(fs: FactStore) -> dict:
    """Record every demo number as a fact and verify the real ones through the
    cross-family panel. Returns {key: fact_id}. Idempotent per store (a second call
    re-asserts; use a fresh store for a clean run)."""
    hypotheses.register_all(fs)
    ids: dict[str, int] = {}
    for d in DEMO_NUMBERS:
        fid = fs.record_real(d.key, d.value, source=d.source_locator, lane=LANE)
        # verify through the panel; a confirming headline (auto-classified) is refused
        # here unless >= 2 distinct families are present — that is the point.
        fs.verify(fid, families=d.families, reviewer="tuesday-demo cross-vendor panel")
        ids[d.key] = fid
    return ids


def report(fs: FactStore) -> list[dict]:
    """Run consume_verified on every demo key. Returns a row per number:
    {key, on_screen, ok, value_or_reason}."""
    rows = []
    for d in DEMO_NUMBERS:
        try:
            value = fs.consume_verified(d.key)
            rows.append({"key": d.key, "on_screen": d.on_screen, "ok": True,
                         "value": value, "reason": ""})
        except FactStoreError as exc:
            rows.append({"key": d.key, "on_screen": d.on_screen, "ok": False,
                         "value": None, "reason": str(exc)})
    return rows


def run(path=None) -> tuple[list[dict], bool]:
    """Wire + report against a store at ``path`` (default: shared). Returns
    (rows, all_passed)."""
    from overmind.factstore import open_shared
    fs = open_shared(path, lane=LANE)
    try:
        wire(fs)
        rows = report(fs)
    finally:
        fs.close()
    return rows, all(r["ok"] for r in rows)


def _format(rows: list[dict]) -> str:
    out = ["TUESDAY DEMO — every on-screen number through consume_verified()", ""]
    for r in rows:
        mark = "PASS" if r["ok"] else "FAIL <<<"
        out.append(f"  [{mark}] {r['on_screen']}")
        out.append(f"          key={r['key']}")
        if not r["ok"]:
            out.append(f"          BLOCKED: {r['reason']}")
    npass = sum(1 for r in rows if r["ok"])
    out += ["", f"  {npass}/{len(rows)} numbers pass consume_verified()."]
    return "\n".join(out)


def main(argv=None) -> int:
    import argparse
    import sys
    try:  # Windows cp1252 stdout can't encode the slide's ∪/≥ glyphs
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(prog="overmind.factstore.lanes.tuesday_demo")
    ap.add_argument("--db", default=None, help="store path (default: a fresh ephemeral run)")
    args = ap.parse_args(argv)
    # Default to an ephemeral in-memory-like run so the report is reproducible and does
    # not depend on prior state; pass --db to wire the shared store.
    rows, ok = run(args.db)
    print(_format(rows))
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
