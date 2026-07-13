"""The minimal CLEAN routed example — every emitted number goes through the sink.

Unlike ``routed_emit`` (which also prints a diagnostic pass/FAIL ledger, and so
trips the scanner on its block-reason prints), this module's ONLY output is the
channel's own ``Rendered.text``. The enforcement scanner classifies it as
``routed``: there is no naked numeric print anywhere. It is the shape every lane
should converge to.
"""
from __future__ import annotations

from overmind.gates.channel import emit
from overmind.gates.contract import Claim, SourceTier


def main() -> int:
    claim = Claim("NCT04336189 arm count", 3, SourceTier.REGISTRY, "NCT04336189#armcount=3")
    print(emit(claim).text)   # arg is emit(...).text -> a routed site, not a leak
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
