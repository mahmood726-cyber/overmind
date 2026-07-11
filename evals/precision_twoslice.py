"""Two-slice frozen validation scorer (the promotion gate I gated on).

Scores the FROZEN WINNING CONFIG — calibrated+method prompt (`_PLUS`) + cross-vendor
corroboration (`arm_c_corroborated`) — on:
  * slice 1 = held-out (developed against): reviews_CALIBRATED_PLUS_COMPLETED.jsonl
  * slice 2 = frozen ∪ dev-cleans (never touched): reviews_CALIBRATED_SLICE2_PLUS.jsonl

Reports FAR + recall with Wilson CIs per slice AND pooled (the public number). NO
tuning — the config is frozen; this only scores. Keys read only here (blinding).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from overmind.benchmark.arms import arm_a, arm_c, arm_c_corroborated  # noqa: E402
from overmind.benchmark.scoring import wilson_ci  # noqa: E402
from overmind.benchmark.tasks import load_keys, load_tasks  # noqa: E402
from evals.precision_measure import _rv, load_reviews  # noqa: E402

DATA = ROOT / "benchmark_data"


def _counts(reviews_path: str, keys, *, arm="corroborated", single_family=False):
    recs = load_reviews(Path(reviews_path))
    ids = [tid for tid in recs if tid in keys]
    caught = defects = fa = cleans = 0
    for tid in ids:
        r = recs[tid]
        cv, av = _rv(r["codex"]), _rv(r["agy"])
        wd = bool(r.get("witness_defect"))
        panel = [av] if single_family else [cv, av]
        if arm == "corroborated":
            v = arm_c_corroborated(tid, panel, wd)
        elif arm == "raw":
            v = arm_c(tid, panel, wd)
        elif arm == "codex":
            v = arm_a(tid, [cv])
        else:
            raise ValueError(arm)
        k = keys[tid]
        if k.has_defect:
            defects += 1; caught += int(v.flag)
        else:
            cleans += 1; fa += int(v.flag)
    return caught, defects, fa, cleans


def _row(label, caught, defects, fa, cleans):
    rec = None if not defects else round(caught / defects, 4)
    far = None if not cleans else round(fa / cleans, 4)
    rc_ci = wilson_ci(caught, defects) if defects else None
    fa_ci = wilson_ci(fa, cleans) if cleans else None
    return {"slice": label, "recall": rec, "recall_ci": rc_ci, "caught": caught,
            "defects": defects, "FAR": far, "FAR_ci": fa_ci, "false_alarms": fa, "cleans": cleans}


def main():
    single = "--single-family" in sys.argv   # agy-only fallback labelling
    keys = load_keys(DATA / "keys" / "keys.json")
    R = DATA / "runs_live_accuracy"
    s1 = Path(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--slice1=")),
                   str(R / "reviews_CALIBRATED_PLUS_COMPLETED.jsonl")))
    s2 = Path(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--slice2=")),
                   str(R / "reviews_CALIBRATED_SLICE2_PLUS.jsonl")))
    arm = "corroborated"
    fam = " [SINGLE-FAMILY agy+floor, consensus DEGRADED — Fix#2 NOT validatable]" if single else ""
    print(f"\n==== TWO-SLICE FROZEN VALIDATION — frozen config (PLUS prompt + {arm}){fam} ====")
    print(f"  slice1={s1.name}\n  slice2={s2.name}")
    rows = []
    c1 = _counts(str(s1), keys, arm=arm, single_family=single)
    rows.append(_row("slice1 held-out (developed)", *c1))
    if s2.exists():
        c2 = _counts(str(s2), keys, arm=arm, single_family=single)
        rows.append(_row("slice2 frozen+devcleans (UNSEEN)", *c2))
        pooled = tuple(a + b for a, b in zip(c1, c2))
        rows.append(_row("POOLED two-slice", *pooled))
    for r in rows:
        rc = f"{r['recall']} {tuple(r['recall_ci']) if r['recall_ci'] else ''}"
        fr = f"{r['FAR']} {tuple(r['FAR_ci']) if r['FAR_ci'] else ''}"
        print(f"  {r['slice']:34} recall={r['caught']}/{r['defects']}={rc:24}  "
              f"FAR={r['false_alarms']}/{r['cleans']}={fr}")
    # fresh-clean-only FAR on slice 2 (the real precision generalisation test)
    if s2.exists():
        _, _, fa2, cl2 = c2
        print(f"\n  >>> slice-2 FRESH-CLEAN FAR (the fragile axis, unseen cleans): "
              f"{fa2}/{cl2} = {round(fa2/cl2,4)} CI{wilson_ci(fa2, cl2)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
