"""A lane that ROUTES its numbers through the binding channel — the pattern.

This is the worked example the other lanes must follow: no number reaches a
human except by ``channel.emit(Claim)``. It is deliberately run against REAL
ground truth (the local AACT snapshot) so the demonstration is not a toy:

  - a real trial datum with a resolvable ``NCT#armcount`` locator PASSES,
    because the resolver follows the pointer into AACT and the value matches;
  - a fabricated NCT (NCT99999999) is BLOCKED — the pointer does not resolve;
  - a synthetic value is BLOCKED — export gate, before resolution;
  - a real trial but a WRONG arm count is BLOCKED — resolves, value mismatches
    (this is the identity gate the corpus run found 136 apps failing);
  - a prose-only locator with no ``#anchor`` is BLOCKED — a citation is not a
    machine pointer.

Because it references ``channel.emit``, the enforcement scanner classifies this
file as ROUTED, not an open hole. That is the whole move: the sink is mandatory
here, and the scanner proves it.
"""
from __future__ import annotations

from dataclasses import dataclass

from overmind.gates.channel import ExportChannel, ChannelViolation
from overmind.gates.contract import Claim, SourceTier


@dataclass(frozen=True, slots=True)
class Demo:
    claim: Claim
    expect: str   # "pass" | "block" — the trip expectation


def _cases() -> list[Demo]:
    return [
        # real trial, arm count pinned to a locator the resolver can follow into AACT
        Demo(Claim("NCT04336189 arm count", 3, SourceTier.REGISTRY,
                   "NCT04336189#armcount=3"), "pass"),
        Demo(Claim("NCT02802501 arm count", 3, SourceTier.REGISTRY,
                   "NCT02802501#armcount=3"), "pass"),
        # fabricated NCT — pointer does not resolve
        Demo(Claim("phantom trial arm count", 2, SourceTier.REGISTRY,
                   "NCT99999999#armcount=2"), "block"),
        # synthetic value — blocked at the export gate, before resolution
        Demo(Claim("DTA70 fabricated sensitivity", 85.8, SourceTier.SYNTHETIC,
                   "NCT01439880#om[1]", synthetic=True), "block"),
        # real trial, WRONG arm count — resolves but value mismatches (identity gate)
        Demo(Claim("NCT01439880 arm count (wrong)", 5, SourceTier.REGISTRY,
                   "NCT01439880#armcount=5"), "block"),
        # prose citation, no machine anchor — a citation is not a pointer
        Demo(Claim("Xpert sensitivity", 0.91, SourceTier.OA_FULLTEXT,
                   "CT.gov NCT04336189 pooled 4 studies"), "block"),
    ]


def run(*, channel: ExportChannel | None = None) -> list[dict]:
    """Route every case through the channel and record what actually happened."""
    ch = channel or ExportChannel()
    rows = []
    for d in _cases():
        try:
            rendered = ch.emit(d.claim, dest="demo")
            rows.append({"claim": d.claim.text, "expect": d.expect, "outcome": "emitted",
                         "gates": rendered.passed_gates,
                         "ground_truth": getattr(rendered.resolution, "ground_truth", None),
                         "ok": d.expect == "pass"})
        except ChannelViolation as exc:
            rows.append({"claim": d.claim.text, "expect": d.expect, "outcome": "blocked",
                         "reason": str(exc), "ok": d.expect == "block"})
    return rows


def main(argv=None) -> int:
    rows = run()
    for r in rows:
        mark = "OK " if r["ok"] else "!! "
        print(f"[{mark}] {r['outcome'].upper():7} (expected {r['expect']}) — {r['claim']}")
        if r["outcome"] == "blocked":
            print(f"        {r['reason'][:140]}")
        else:
            print(f"        gates={r['gates']} ground_truth={r.get('ground_truth')}")
    n_ok = sum(1 for r in rows if r["ok"])
    print(f"\n{n_ok}/{len(rows)} cases behaved as the contract requires.")
    return 0 if n_ok == len(rows) else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
