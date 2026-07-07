"""Reconstruct the full held-out Arm C with the FIXED agy backend + conformal gate.

The async-envelope fix only changes agy's verdict on the tasks where it previously
returned an envelope (or the false-alarm over-reads). Those affected tasks are
re-measured live (scripts scratchpad agy_recheck.json); the other agy reviews were
already usable and are carried forward from the captured run. This splices the
re-measured agy verdicts into the captured Arm-C panel, re-derives Arm C (fixed agy
reviewer + Claude + witness floor), applies the calibrated conformal gate, and
scores the full 139-task held-out slice — the definitive combined result.

Usage: python scripts/benchmark_splice_agyfix.py [--alpha 0.05] [--recheck <json>]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

OVR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OVR))

from overmind.benchmark.arms import arm_c                            # noqa: E402
from overmind.benchmark.conformal import gate_from_defect_flags     # noqa: E402
from overmind.benchmark.reviewers import ReviewerVerdict            # noqa: E402
from overmind.benchmark.scoring import score_arm, evaluate_win_condition, two_slice_promotion  # noqa: E402
from overmind.benchmark.runner import _verdict_from_dict            # noqa: E402
from overmind.benchmark.tasks import load_keys, load_tasks, held_out_ids, frozen_ids  # noqa: E402

DATA = OVR / "benchmark_data"


def load_arm(rundir: str, arm: str) -> dict:
    p = DATA / rundir / f"arm_{arm}.jsonl"
    out = {}
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln:
                r = json.loads(ln); out[r["task_id"]] = r
    return out


def revs(rec: dict) -> list[ReviewerVerdict]:
    return [ReviewerVerdict(flag=bool(x.get("flag")), reason=x.get("reason", "") or "",
                            vendor=x.get("vendor", "") or "", usable=bool(x.get("usable", True)))
            for x in rec.get("reviewers", [])]


def splice_agy(rec: dict, new_agy: dict | None) -> list[ReviewerVerdict]:
    """Return the panel with agy's verdict replaced by the re-measured one."""
    panel = []
    for x in rec.get("reviewers", []):
        if x.get("vendor") == "agy" and new_agy is not None:
            panel.append(ReviewerVerdict(flag=bool(new_agy["flag"]), reason=new_agy.get("reason", ""),
                                         vendor="agy", usable=bool(new_agy["usable"])))
        else:
            panel.append(ReviewerVerdict(flag=bool(x.get("flag")), reason=x.get("reason", "") or "",
                                         vendor=x.get("vendor", "") or "", usable=bool(x.get("usable", True))))
    return panel


def main() -> int:
    alpha = 0.05
    if "--alpha" in sys.argv:
        alpha = float(sys.argv[sys.argv.index("--alpha") + 1])
    recheck_path = DATA / "runs_live" / "agy_recheck.json"
    if "--recheck" in sys.argv:
        recheck_path = Path(sys.argv[sys.argv.index("--recheck") + 1])
    recheck = json.loads(recheck_path.read_text(encoding="utf-8"))
    new_agy = {r["id"]: r for grp in recheck.values() for r in grp}

    tasks = {t.id: t for t in load_tasks(DATA / "tasks.json")}
    keys = load_keys(DATA / "keys" / "keys.json")
    ids = list(tasks)
    ho = held_out_ids(ids); fz = frozen_ids(ids)

    A = load_arm("runs_live", "A"); B = load_arm("runs_live", "B"); C = load_arm("runs_live", "C")
    sk = {t: keys[t] for t in C if t in ho and t in keys}
    defect_ids = {t for t, k in sk.items() if k.has_defect}

    # panels with the fixed agy spliced in
    spliced = {t: splice_agy(C[t], new_agy.get(t)) for t in C if t in sk}

    # calibrate the conformal gate on the (fixed) defect flags
    revs_by_task = {t: [{"flag": v.flag, "reason": v.reason, "vendor": v.vendor, "usable": v.usable}
                        for v in spliced[t]] for t in spliced}
    gate = gate_from_defect_flags(revs_by_task, defect_ids, alpha=alpha)

    # Arm C: fixed agy + witness floor, no gate vs gated
    C_fix = {t: arm_c(t, spliced[t], bool(C[t].get("witness_defect")), gate=None) for t in spliced}
    C_fix_gate = {t: arm_c(t, spliced[t], bool(C[t].get("witness_defect")), gate=gate) for t in spliced}
    Av = {t: _verdict_from_dict(A[t]) for t in A if t in sk}
    Bv = {t: _verdict_from_dict(B[t]) for t in B if t in sk}

    ma = score_arm("A", Av, sk); mb = score_arm("B", Bv, sk)
    mc_fix = score_arm("C(agy-fix)", C_fix, sk)
    mc_both = score_arm("C(agy-fix+conformal)", C_fix_gate, sk)

    # frozen: conformal only (agy re-check is held-out; frozen carried from captured run)
    fz_sk = {t: keys[t] for t in load_arm("runs_frozen", "C") if t in fz and t in keys}
    FC = load_arm("runs_frozen", "C"); FA = load_arm("runs_frozen", "A"); FB = load_arm("runs_frozen", "B")
    fz_defect = {t for t, k in fz_sk.items() if k.has_defect}
    fgate = gate_from_defect_flags({t: FC[t].get("reviewers", []) for t in FC}, fz_defect, alpha=alpha)
    FCg = {t: arm_c(t, revs(FC[t]), bool(FC[t].get("witness_defect")), gate=fgate) for t in FC if t in fz_sk}
    fma = score_arm("A", {t: _verdict_from_dict(FA[t]) for t in FA if t in fz_sk}, fz_sk)
    fmb = score_arm("B", {t: _verdict_from_dict(FB[t]) for t in FB if t in fz_sk}, fz_sk)
    fmc = score_arm("C", FCg, fz_sk)

    print(f"\n===== COMBINED (agy-fix + conformal alpha={alpha}, tau={gate.tau:.3f}) — HELD-OUT 139 =====")
    for m in (ma, mb, mc_fix, mc_both):
        print(f"  {m.arm:24} caught={m.caught}/{m.defects}={m.caught_defect_rate}  "
              f"FAR={m.false_alarms}/{m.cleans}={m.false_alarm_rate}  agree={m.agreement_soundness}  "
              f"blended={m.blended}  (abstain {m.abstained})")
    print(f"  C caught CI95: {mc_both.caught_defect_ci}")
    wc = evaluate_win_condition(ma, mb, mc_both)
    print(f"  WIN CONDITION: {wc.verdict}  c_beats_a={wc.c_beats_a} c_beats_b={wc.c_beats_b} affordable={wc.affordable}")
    for n in wc.notes:
        print("    note:", n)

    print(f"\n  FROZEN 73 (conformal, tau={fgate.tau:.3f}):")
    for m in (fma, fmb, fmc):
        print(f"    {m.arm}: caught={m.caught_defect_rate} blended={m.blended}")
    ho_inc = max(ma.blended, mb.blended); fz_inc = max(fma.blended, fmb.blended)
    tsp = two_slice_promotion(ho_inc, mc_both.blended, fz_inc, fmc.blended)
    print(f"  TWO-SLICE (C vs best-of-AB blended): held-out {mc_both.blended} vs {ho_inc}; "
          f"frozen {fmc.blended} vs {fz_inc} -> promote={tsp.promote}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
