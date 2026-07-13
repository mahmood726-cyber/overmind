"""Retroactively seed EVERY known-bad artefact synthetic in the SHARED store, so any
lane consuming those keys is BLOCKED live (CLI ``consume`` -> exit 3). This extends
``seed_dta70`` from the single DTA70 figure to the full known-bad set:

  * fake 17-study Xpert Se 85.8 / Sp 97.8  (DTA70; also fails plausibility)
  * R21 VE 44%  (true 73%)
  * Nix-TB 32/109 control (NCT02333799; single-arm trial)
  * tirzepatide cN=1 (NCT03730662; broken denominator)
  * OJS hardcoded counts (ZOO_G=432, ZOO_A=99, AMR_G=259, AMR_A=47)

Idempotent: a key already recorded synthetic is left alone. Run as a module to seed
the shared store and print a live proof that each key is now unconsumable.
"""
from __future__ import annotations

from overmind.factstore import open_shared, Provenance
from overmind.factstore.lanes.known_bad import KNOWN_BAD, LANE


def seed(path=None) -> list[int]:
    """Seed the shared store (or ``path``) with every known-bad artefact synthetic.
    Returns the fact ids."""
    fs = open_shared(path, lane=LANE)
    ids = []
    try:
        for b in KNOWN_BAD:
            existing = fs.facts_for(b.key)
            already = [f for f in existing
                       if f.provenance == Provenance.SYNTHETIC and f.value == b.value]
            if already:
                ids.append(already[-1].id)
                continue
            ids.append(fs.record_synthetic(
                b.key, b.value, source=f"KNOWN-BAD: {b.why_bad}", lane=LANE,
                derivation="retroactive quarantine of a known-bad artefact"))
    finally:
        fs.close()
    return ids


def main(argv=None) -> int:
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    import argparse
    ap = argparse.ArgumentParser(prog="overmind.factstore.seed_known_bad")
    ap.add_argument("--db", default=None, help="store path (default: shared)")
    args = ap.parse_args(argv)
    ids = seed(args.db)
    print(f"seeded {len(ids)} known-bad synthetic facts into the shared store")
    fs = open_shared(args.db, lane="proof")
    blocked = 0
    try:
        for b in KNOWN_BAD:
            ok, reason = fs.try_consume(b.key)
            status = "RETURNED A VALUE (BUG!)" if ok else "BLOCKED"
            if not ok:
                blocked += 1
            print(f"  consume {b.key!r}: {status}")
    finally:
        fs.close()
    print(f"{blocked}/{len(KNOWN_BAD)} known-bad keys blocked live")
    return 0 if blocked == len(KNOWN_BAD) else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
