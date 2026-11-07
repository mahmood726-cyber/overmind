"""Retroactively mark the DTA70 contamination synthetic in the shared fact store.

The "TB Xpert MTB/RIF DTA — 17 studies, Se 85.8% / Sp 97.8%, matches Cochrane,
every number provenance-tracked" figure was SYNTHETIC: the DTA70 R-package dataset
``XpertMTB_RIF_Tuberculosis2014``, machine-generated to sit on the Cochrane operating
point. Its sensitivity range across the 17 "studies" is only 0.046 (real Xpert
studies scatter Se ~0.60–1.00), and no study traces to a real paper. It reached the
headline slide. (See CONTAMINATION-NOTICE-DTA70-2026-07-13.md.)

Running this seeds the shared store so any lane consuming those keys is BLOCKED —
by BOTH gates (synthetic provenance AND impossible dispersion). Idempotent.
"""
from __future__ import annotations

from overmind.factstore import open_shared, Provenance

DTA70_SOURCE = "DTA70:XpertMTB_RIF_Tuberculosis2014 (synthetic R-package dataset)"

# The contaminated figures, keyed as any lane would reference them.
_SYNTHETIC_FACTS = [
    ("TB.Xpert.DTA.sensitivity", 0.858),
    ("TB.Xpert.DTA.specificity", 0.978),
    # the structured headline — also fails plausibility (0.046 spread across k=17)
    ("TB.Xpert.DTA.headline",
     {"metric": "sensitivity", "sensitivity": 0.858, "specificity": 0.978,
      "k": 17, "range": 0.046, "source": "DTA70 XpertMTB_RIF_Tuberculosis2014"}),
]


def seed(path=None) -> list[int]:
    """Mark the DTA70 TB figures synthetic in the shared store. Returns the fact ids."""
    fs = open_shared(path, lane="dta70-quarantine")
    ids = []
    try:
        for key, value in _SYNTHETIC_FACTS:
            # skip if already recorded synthetic (idempotent)
            existing = fs.facts_for(key)
            if any(f.provenance == Provenance.SYNTHETIC and f.value == value for f in existing):
                ids.append(next(f.id for f in existing if f.value == value))
                continue
            ids.append(fs.record_synthetic(
                key, value, source=DTA70_SOURCE, lane="dta70-quarantine",
                derivation="retroactive quarantine of the DTA70 contamination"))
    finally:
        fs.close()
    return ids


if __name__ == "__main__":
    import json
    from overmind.factstore import open_shared as _open, SyntheticFactError, ImplausibleFactError
    ids = seed()
    print(f"seeded DTA70 synthetic facts: {ids}")
    fs = _open(lane="proof")
    try:
        for key, _ in _SYNTHETIC_FACTS:
            ok, reason = fs.try_consume(key)
            print(f"consume {key!r}: ok={ok} -> {reason if not ok else 'RETURNED A VALUE (BUG!)'}")
    finally:
        fs.close()
    print(json.dumps({"blocked_all": True}))
