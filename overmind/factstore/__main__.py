"""CLI for the shared fact store — so ANY lane, in ANY repo or language, can join
the store with one shell line (no Python import needed):

    python -m overmind.factstore record --key TB.DTA.sens --value 0.858 \
        --provenance synthetic --source DTA70 --lane my-lane
    python -m overmind.factstore consume --key TB.DTA.sens   # exit!=0 + reason if blocked

`consume` exits non-zero and prints the reason on any block (synthetic / unverified /
contradicted / implausible), so a shell pipeline fails loud rather than emitting a
naked number. Value is parsed as JSON when possible, else kept as a string.
"""
from __future__ import annotations

import argparse
import json
import sys

from overmind.factstore import FactStore, open_shared, FactStoreError, check_plausibility


def _parse_value(s: str):
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return s


def _store(args) -> FactStore:
    return open_shared(args.db, lane=getattr(args, "lane", None))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="overmind.factstore", description=__doc__)
    ap.add_argument("--db", default=None, help="store path (default: OVERMIND_FACTSTORE or ~/.overmind/factstore.db)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("record", help="append a fact")
    r.add_argument("--key", required=True)
    r.add_argument("--value", required=True)
    r.add_argument("--provenance", choices=["real", "synthetic"], default="real")
    r.add_argument("--source", required=True)
    r.add_argument("--lane", required=True)
    r.add_argument("--derivation", default="")
    r.add_argument("--parents", default="", help="comma-separated parent fact ids")
    r.add_argument("--confirms", action="store_true", help="this confirms a hypothesis")
    r.add_argument("--hypothesis", default="")
    r.add_argument("--refutation", default="")

    v = sub.add_parser("verify", help="record a verification")
    v.add_argument("--id", type=int, required=True)
    v.add_argument("--families", required=True, help="comma-separated vendor families")
    v.add_argument("--reviewer", default="")
    v.add_argument("--lane", default=None)

    c = sub.add_parser("consume", help="print a key's verified value or FAIL LOUD")
    c.add_argument("--key", required=True)
    c.add_argument("--lane", default=None)

    p = sub.add_parser("check", help="run the plausibility gate on a value")
    p.add_argument("--value", required=True)
    p.add_argument("--kind", default=None)

    ls = sub.add_parser("list", help="list facts (optionally for one key)")
    ls.add_argument("--key", default=None)
    ls.add_argument("--lane", default=None)

    args = ap.parse_args(argv)

    if args.cmd == "check":
        res = check_plausibility(_parse_value(args.value), kind=args.kind)
        print(json.dumps(res.to_dict()))
        return 0 if res.ok else 2

    fs = _store(args)
    try:
        if args.cmd == "record":
            parents = [int(x) for x in args.parents.split(",") if x.strip()]
            fid = fs.assert_fact(
                args.key, _parse_value(args.value), provenance=args.provenance,
                source_locator=args.source, lane=args.lane, derivation=args.derivation,
                parents=parents, confirms_hypothesis=args.confirms,
                hypothesis=args.hypothesis, refutation_criterion=args.refutation)
            print(json.dumps(fs.get(fid).to_dict()))
            return 0
        if args.cmd == "verify":
            fams = [f for f in args.families.split(",") if f.strip()]
            fs.verify(args.id, families=fams, reviewer=args.reviewer)
            print(json.dumps({"verified": args.id, "families": fams}))
            return 0
        if args.cmd == "consume":
            try:
                value = fs.consume_verified(args.key)
                print(json.dumps({"key": args.key, "value": value}))
                return 0
            except FactStoreError as exc:
                print(f"BLOCKED: {exc}", file=sys.stderr)
                return 3
        if args.cmd == "list":
            facts = fs.facts_for(args.key) if args.key else fs.all_facts()
            print(json.dumps([f.to_dict() for f in facts], indent=2))
            return 0
    finally:
        fs.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
