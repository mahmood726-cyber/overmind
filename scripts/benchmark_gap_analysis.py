"""Gap analysis: classify every Arm-C miss + false alarm by failure mode.

Joins the sealed answer keys with a run's arm_{A,B,C}.jsonl and, for Arm C,
buckets each residual into the failure modes Mahmood asked for:

  witness_floor_gap        - witness-detectable defect the objective floor MISSED
                             (-> expand objective witnesses; cheap, high value)
  correlated_blind_spot    - reviewer-only defect ALL usable vendors missed
                             (-> a genuinely-different vendor / targeted prompt)
  degraded_vendor_loss     - reviewer-only miss where a vendor was UNUSABLE
                             (a catch may have been lost to throttling)
  aggregation_suppressed   - a vendor flagged but the rule suppressed it
                             (impossible under consensus-or-flag; reported if seen)
  false_alarm_calibration  - clean task flagged (which vendor cried wolf)
                             (-> conformal accept/abstain gate)

Also decomposes the WIN sources: witness-detectable caught by the floor vs
reviewer-only caught by each vendor, and A/B/C head-to-head per source.

Usage: python gap_analysis.py <run_dir> <slice: held_out|frozen> [--json out.json]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

OVR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OVR))
from overmind.benchmark.tasks import (  # noqa: E402
    load_keys, load_tasks, held_out_ids, frozen_ids,
    WITNESS_DETECTABLE_KINDS, REVIEWER_ONLY_KINDS,
)

DATA = OVR / "benchmark_data"


def load_arm(run_dir: Path, arm: str) -> dict:
    """task_id -> record (last write wins on resume dupes)."""
    p = run_dir / f"arm_{arm}.jsonl"
    out = {}
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        out[r["task_id"]] = r
    return out


def rev_map(rec: dict) -> dict:
    """vendor -> (flag, usable) from a verdict record's reviewer list."""
    m = {}
    for rv in rec.get("reviewers", []):
        m[rv.get("vendor", "?")] = (bool(rv.get("flag")), bool(rv.get("usable", True)))
    return m


def main() -> int:
    run_dir = Path(sys.argv[1])
    which = sys.argv[2]
    json_out = None
    if "--json" in sys.argv:
        json_out = sys.argv[sys.argv.index("--json") + 1]

    tasks = load_tasks(DATA / "tasks.json")
    keys = load_keys(DATA / "keys" / "keys.json")
    ids = [t.id for t in tasks]
    slice_ids = held_out_ids(ids) if which == "held_out" else frozen_ids(ids)

    A = load_arm(run_dir, "A")
    B = load_arm(run_dir, "B")
    C = load_arm(run_dir, "C")
    scored_ids = [tid for tid in slice_ids if tid in C]  # only tasks C actually ran

    # per-arm tallies
    def tally(arm_recs):
        caught = defects = fa = cleans = 0
        for tid in scored_ids:
            k = keys.get(tid)
            r = arm_recs.get(tid)
            if k is None or r is None:
                continue
            if k.has_defect:
                defects += 1
                if r["flag"]:
                    caught += 1
            else:
                cleans += 1
                if r["flag"]:
                    fa += 1
        return caught, defects, fa, cleans

    res = {"run_dir": str(run_dir), "slice": which, "scored_n": len(scored_ids),
           "arms": {}, "win_decomp": {}, "C_misses": [], "C_false_alarms": [],
           "failure_modes": {}}

    for name, recs in (("A", A), ("B", B), ("C", C)):
        if not recs:
            continue
        c, d, fa, cl = tally(recs)
        res["arms"][name] = {"caught": c, "defects": d, "caught_rate": round(c / d, 4) if d else None,
                             "false_alarms": fa, "cleans": cl,
                             "far": round(fa / cl, 4) if cl else None}

    # win decomposition by SOURCE (witness-detectable vs reviewer-only)
    wd = {"A": 0, "B": 0, "C": 0, "n": 0}
    ro = {"A": 0, "B": 0, "C": 0, "n": 0}
    for tid in scored_ids:
        k = keys.get(tid)
        if not k or not k.has_defect:
            continue
        kind = C[tid]["kind"]
        bucket = wd if kind in WITNESS_DETECTABLE_KINDS else ro
        bucket["n"] += 1
        for name, recs in (("A", A), ("B", B), ("C", C)):
            if tid in recs and recs[tid]["flag"]:
                bucket[name] += 1
    res["win_decomp"] = {"witness_detectable": wd, "reviewer_only": ro}

    # per-vendor reviewer-only catch (how much a 2nd vendor adds on floor-invisible defects)
    vendor_ro_catch = {}
    vendor_ro_usable = {}
    for tid in scored_ids:
        k = keys.get(tid)
        if not k or not k.has_defect:
            continue
        if C[tid]["kind"] not in REVIEWER_ONLY_KINDS:
            continue
        for v, (flag, usable) in rev_map(C[tid]).items():
            vendor_ro_usable[v] = vendor_ro_usable.get(v, 0) + (1 if usable else 0)
            if flag:
                vendor_ro_catch[v] = vendor_ro_catch.get(v, 0) + 1
    res["reviewer_only_by_vendor"] = {"catch": vendor_ro_catch, "usable": vendor_ro_usable,
                                      "n_reviewer_only_defects": ro["n"]}

    # classify every C miss + false alarm
    fm = {"witness_floor_gap": [], "correlated_blind_spot": [],
          "degraded_vendor_loss": [], "aggregation_suppressed": [],
          "false_alarm_calibration": []}
    for tid in scored_ids:
        k = keys.get(tid)
        r = C.get(tid)
        if not k or not r:
            continue
        kind = r["kind"]
        rm = rev_map(r)
        if k.has_defect and not r["flag"]:  # MISS
            entry = {"id": tid, "kind": kind, "witness_defect": r.get("witness_defect"),
                     "reviewers": {v: {"flag": f, "usable": u} for v, (f, u) in rm.items()},
                     "note": k.note}
            if kind in WITNESS_DETECTABLE_KINDS:
                fm["witness_floor_gap"].append(entry)
            else:
                any_unusable = any(not u for (_, u) in rm.values())
                any_flag_but_missed = any(f for (f, _) in rm.values())  # would signal suppression
                if any_flag_but_missed:
                    fm["aggregation_suppressed"].append(entry)
                elif any_unusable:
                    fm["degraded_vendor_loss"].append(entry)
                else:
                    fm["correlated_blind_spot"].append(entry)
            res["C_misses"].append(entry)
        elif (not k.has_defect) and r["flag"]:  # FALSE ALARM
            culprits = {v: rm[v] for v in rm if rm[v][0]}
            entry = {"id": tid, "kind": kind, "deciding": r.get("deciding"),
                     "flagging_vendors": list(culprits.keys()),
                     "reasons": {rv.get("vendor"): rv.get("reason", "")[:120]
                                 for rv in r.get("reviewers", []) if rv.get("flag")}}
            fm["false_alarm_calibration"].append(entry)
            res["C_false_alarms"].append(entry)

    res["failure_modes"] = {k: len(v) for k, v in fm.items()}
    res["failure_modes_detail"] = fm

    # miss breakdown by kind
    miss_by_kind = {}
    for m in res["C_misses"]:
        miss_by_kind[m["kind"]] = miss_by_kind.get(m["kind"], 0) + 1
    res["C_miss_by_kind"] = miss_by_kind

    # ---- print human summary ----
    print(f"\n===== GAP ANALYSIS: {which} slice, run={run_dir.name}, scored={len(scored_ids)} =====")
    for name in ("A", "B", "C"):
        if name in res["arms"]:
            a = res["arms"][name]
            print(f"  Arm {name}: caught {a['caught']}/{a['defects']} = {a['caught_rate']}  "
                  f"FAR {a['false_alarms']}/{a['cleans']} = {a['far']}")
    print(f"\n  WIN DECOMP  witness-detectable (n={wd['n']}): A={wd['A']} B={wd['B']} C={wd['C']}")
    print(f"              reviewer-only     (n={ro['n']}): A={ro['A']} B={ro['B']} C={ro['C']}")
    print(f"  reviewer-only catch by vendor: {vendor_ro_catch}  (usable: {vendor_ro_usable})")
    print(f"\n  C MISSES: {len(res['C_misses'])}  by kind: {miss_by_kind}")
    print(f"  C FALSE ALARMS: {len(res['C_false_alarms'])}")
    print(f"\n  FAILURE MODES:")
    for k, v in res["failure_modes"].items():
        print(f"    {k}: {v}")

    if json_out:
        Path(json_out).write_text(json.dumps(res, indent=1), encoding="utf-8")
        print(f"\n  -> {json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
