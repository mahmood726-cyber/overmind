"""Seed EVERY known-bad artefact synthetic and prove each is unconsumable.

Not just DTA70. Each of these was a real defect that did (or nearly did) reach a
shipped claim; seeding it here means any lane that references its key is BLOCKED at
``consume_verified`` (CLI exit 3) instead of emitting a naked number. The point of
running this in the SAME store as ``tuesday_demo`` is Mahmood's real question:
*could a fabricated figure still reach a slide?* — the real demo numbers pass while
these are blocked, side by side.

Artefacts:
  * fake 17-study Xpert Se 85.8 / Sp 97.8  — DTA70 synthetic + impossible dispersion
  * R21 VE 44%  (true 73%, 464/3102)       — fabricated/mislabeled efficacy
  * Nix-TB 32/109 control (NCT02333799)    — fabricated comparator (trial is single-arm)
  * tirzepatide cN=1 (NCT03730662)         — broken denominator (control N=1)
  * OJS hardcoded counts (ZOO/AMR)         — literals typed into a dashboard, no source
"""
from __future__ import annotations

from dataclasses import dataclass, field

from overmind.factstore.store import FactStore, FactStoreError
from overmind.factstore import check_plausibility

LANE = "known-bad-quarantine"


@dataclass(slots=True)
class BadArtefact:
    key: str
    value: object
    what: str                 # human description of the number
    why_bad: str              # why it must never be consumed
    also_implausible: bool = False   # expect the plausibility gate to ALSO catch it
    truth: str = ""           # the correct value, where one exists


KNOWN_BAD: list[BadArtefact] = [
    BadArtefact(
        "TB.Xpert.fake17.headline",
        {"metric": "sensitivity", "sensitivity": 0.858, "specificity": 0.978,
         "k": 17, "range": 0.046,
         "source": "DTA70 XpertMTB_RIF_Tuberculosis2014 (synthetic R-package dataset)"},
        "fake 17-study Xpert MTB/RIF DTA, Se 85.8% / Sp 97.8%",
        "DTA70 synthetic dataset; all 17 'studies' sit at Se≈0.86 — a 0.046 sensitivity "
        "spread across 17 real studies is impossible; no study traces to a real paper. "
        "It reached the headline slide before it was caught.",
        also_implausible=True,
        truth="real 4-study pool Se 91.0 / Sp 99.0 (xpert-tb.html)"),
    BadArtefact(
        "TB.Xpert.fake17.sensitivity", 0.858,
        "fake 17-study Xpert sensitivity 0.858",
        "DTA70 synthetic; the scalar carrier of the same fabrication.",
        truth="0.910 (real 4-study)"),
    BadArtefact(
        "TB.Xpert.fake17.specificity", 0.978,
        "fake 17-study Xpert specificity 0.978",
        "DTA70 synthetic; the scalar carrier of the same fabrication.",
        truth="0.990 (real 4-study)"),
    BadArtefact(
        "malaria.R21.VE", 0.44,
        "R21 malaria vaccine efficacy 44%",
        "Fabricated/mislabeled efficacy — not traceable to the trial; the real R21 "
        "efficacy is 73% (464/3102, combined). 44% is not a value any arm reports.",
        truth="0.73 (VE 73%, 464/3102; 75%/68% by season flag)"),
    BadArtefact(
        "TB.NixTB.control", {"events_c": 32, "n_c": 109, "arm": "control"},
        "Nix-TB control arm 32/109",
        "Fabricated comparator: Nix-TB (NCT02333799) is a SINGLE-ARM trial — it has no "
        "control arm, so a 32/109 control is invented.",
        truth="no control arm exists (single-arm BPaL study)"),
    BadArtefact(
        "diabetes.tirzepatide.control", {"events_c": 0, "n_c": 1, "arm": "control"},
        "tirzepatide control arm N=1",
        "Broken denominator: control N=1 (NCT03730662). A one-patient control arm is a "
        "data-integrity failure, not a comparator.",
        truth="broken denominator — arm mapping missing from the snapshot"),
    BadArtefact(
        "ojs.ZOO.gold_count", 432,
        "OJS ZOO_G (gold count) = 432",
        "Hardcoded literal typed into the OJS dashboard, not derived from any corpus — "
        "no source, no provenance.",
        truth="must be re-derived from the corpus, not hardcoded"),
    BadArtefact(
        "ojs.ZOO.audit_count", 99,
        "OJS ZOO_A (audit count) = 99",
        "Hardcoded literal in the OJS dashboard; no source.",
        truth="re-derive from corpus"),
    BadArtefact(
        "ojs.AMR.gold_count", 259,
        "OJS AMR_G (gold count) = 259",
        "Hardcoded literal in the OJS dashboard; no source.",
        truth="re-derive from corpus"),
    BadArtefact(
        "ojs.AMR.audit_count", 47,
        "OJS AMR_A (audit count) = 47",
        "Hardcoded literal in the OJS dashboard; no source.",
        truth="re-derive from corpus"),
]


def seed(fs: FactStore) -> dict:
    """Record every known-bad artefact SYNTHETIC. Idempotent-ish: appends synthetic
    facts (a synthetic key is unconsumable regardless of duplicates). Returns
    {key: fact_id}."""
    ids: dict[str, int] = {}
    for b in KNOWN_BAD:
        fid = fs.record_synthetic(
            b.key, b.value, source=f"KNOWN-BAD: {b.why_bad}", lane=LANE,
            derivation="retroactive quarantine of a known-bad artefact")
        ids[b.key] = fid
    return ids


def prove_blocked(fs: FactStore) -> list[dict]:
    """Try to consume every known-bad key. Each MUST be blocked. Returns a row per
    artefact: {key, what, blocked, reason, plausibility_ok, plausibility_reasons}."""
    rows = []
    for b in KNOWN_BAD:
        try:
            fs.consume_verified(b.key)
            blocked, reason = False, "!!! CONSUMED A KNOWN-BAD NUMBER (GATE FAILED) !!!"
        except FactStoreError as exc:
            blocked, reason = True, str(exc)
        plaus = check_plausibility(b.value, kind=b.key)
        rows.append({
            "key": b.key, "what": b.what, "blocked": blocked, "reason": reason,
            "truth": b.truth,
            "plausibility_ok": plaus.ok,
            "plausibility_reasons": plaus.violations,
            "expected_implausible": b.also_implausible,
        })
    return rows


def _format(rows: list[dict]) -> str:
    out = ["KNOWN-BAD ARTEFACTS — every one must be BLOCKED at consume_verified()", ""]
    for r in rows:
        mark = "BLOCKED" if r["blocked"] else "LEAKED <<< DANGER"
        out.append(f"  [{mark}] {r['what']}")
        out.append(f"           key={r['key']}")
        out.append(f"           reason: {r['reason'][:140]}")
        if not r["plausibility_ok"]:
            out.append(f"           ALSO implausible: {'; '.join(r['plausibility_reasons'])[:140]}")
        if r["truth"]:
            out.append(f"           truth: {r['truth']}")
    nblocked = sum(1 for r in rows if r["blocked"])
    out += ["", f"  {nblocked}/{len(rows)} known-bad artefacts blocked."]
    return "\n".join(out)


def run(path=None) -> tuple[list[dict], bool]:
    from overmind.factstore import open_shared
    fs = open_shared(path, lane=LANE)
    try:
        seed(fs)
        rows = prove_blocked(fs)
    finally:
        fs.close()
    return rows, all(r["blocked"] for r in rows)


def main(argv=None) -> int:
    import argparse
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(prog="overmind.factstore.lanes.known_bad")
    ap.add_argument("--db", default=None)
    args = ap.parse_args(argv)
    rows, all_blocked = run(args.db)
    print(_format(rows))
    # exit non-zero if ANY known-bad artefact was consumable (that would be the disaster)
    return 0 if all_blocked else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
