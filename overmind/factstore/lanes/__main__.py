"""Flagship proof: run the Tuesday demo lane and the known-bad artefacts in ONE
shared store and answer Mahmood's question directly — *could a fabricated figure
still reach a slide?*

    python -m overmind.factstore.lanes            # ephemeral, reproducible
    python -m overmind.factstore.lanes --db PATH   # wire a real shared store

Every real on-screen demo number must PASS ``consume_verified`` and every known-bad
artefact must be BLOCKED, side by side in the same store. Exits non-zero if any demo
number fails to verify OR any known-bad number leaks — either is a release blocker.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from overmind.factstore import open_shared
from overmind.factstore.lanes import tuesday_demo, known_bad, other_lanes


def run(path=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    ephemeral = path is None
    if ephemeral:
        tmp = tempfile.mkdtemp(prefix="factstore-lanes-")
        path = str(Path(tmp) / "lanes.db")

    # ONE store, all lanes + the known-bad artefacts.
    fs = open_shared(path, lane="lanes-runner")
    try:
        tuesday_demo.wire(fs)
        other_lanes.wire(fs)
        known_bad.seed(fs)
        demo_rows = tuesday_demo.report(fs)
        other_rows = other_lanes.report(fs)
        bad_rows = known_bad.prove_blocked(fs)
    finally:
        fs.close()

    print(tuesday_demo._format(demo_rows))
    print()
    print(other_lanes._format(other_rows))
    print()
    print(known_bad._format(bad_rows))
    print()

    demo_ok = all(r["ok"] for r in demo_rows)
    other_ok = all(r["ok"] for r in other_rows)
    bad_ok = all(r["blocked"] for r in bad_rows)
    leaks = [r["key"] for r in bad_rows if not r["blocked"]]
    fails = [r["key"] for r in demo_rows + other_rows if not r["ok"]]
    print("=" * 70)
    print(f"Could a fabricated figure reach a slide?  "
          f"{'NO — every known-bad number is blocked.' if bad_ok else 'YES — LEAK: ' + ', '.join(leaks)}")
    print(f"Do the real lane numbers survive the gate? "
          f"{'YES — all ' + str(len(demo_rows) + len(other_rows)) + ' pass.' if (demo_ok and other_ok) else 'NO — FAIL: ' + ', '.join(fails)}")
    print(f"Store: {path}")
    return 0 if (demo_ok and other_ok and bad_ok) else 1


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="overmind.factstore.lanes")
    ap.add_argument("--db", default=None,
                    help="store path (default: fresh ephemeral, reproducible)")
    args = ap.parse_args(argv)
    return run(args.db)


if __name__ == "__main__":
    sys.exit(main())
