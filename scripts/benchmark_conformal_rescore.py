"""Re-score a captured A/B/C run through the conformal accept/abstain gate (PV-B).

This applies the gate to the ALREADY-CAPTURED Arm-C reviewer records — no model
calls — so the false-alarm fix can be measured on the exact same reviews the live
run produced. The gate is calibrated on the DEFECT class only (retain >= 1-alpha of
catches); the clean-task false-alarm reduction is the out-of-sample consequence.

Usage:
    python scripts/benchmark_conformal_rescore.py <run_dir> <held_out|frozen> [--alpha 0.05]
    python scripts/benchmark_conformal_rescore.py benchmark_data/runs_live held_out
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

OVR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OVR))

from overmind.benchmark.arms import arm_c                            # noqa: E402
from overmind.benchmark.conformal import gate_from_defect_flags, flag_confidence  # noqa: E402
from overmind.benchmark.reviewers import ReviewerVerdict            # noqa: E402
from overmind.benchmark.scoring import score_arm                    # noqa: E402
from overmind.benchmark.tasks import load_keys, load_tasks, held_out_ids, frozen_ids  # noqa: E402

DATA = OVR / "benchmark_data"


def load_arm(run_dir: Path, arm: str) -> dict:
    p = run_dir / f"arm_{arm}.jsonl"
    out = {}
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            r = json.loads(line)
            out[r["task_id"]] = r
    return out


def revs_of(rec: dict) -> list[ReviewerVerdict]:
    return [ReviewerVerdict(flag=bool(rv.get("flag")), reason=rv.get("reason", "") or "",
                            vendor=rv.get("vendor", "") or "", usable=bool(rv.get("usable", True)))
            for rv in rec.get("reviewers", [])]


def rebuild_verdicts(C: dict, keys: dict, gate) -> dict:
    """Re-derive each Arm-C verdict from its captured reviewers + witness, applying
    the gate. Uses the recorded witness_defect (the deterministic floor is unchanged)."""
    out = {}
    for tid, rec in C.items():
        revs = revs_of(rec)
        witness = bool(rec.get("witness_defect"))
        out[tid] = arm_c(tid, revs, witness, gate=gate)
    return out


def main() -> int:
    run_dir = Path(sys.argv[1])
    which = sys.argv[2]
    alpha = 0.05
    if "--alpha" in sys.argv:
        alpha = float(sys.argv[sys.argv.index("--alpha") + 1])

    tasks = load_tasks(DATA / "tasks.json")
    keys = load_keys(DATA / "keys" / "keys.json")
    ids = [t.id for t in tasks]
    slice_ids = held_out_ids(ids) if which == "held_out" else frozen_ids(ids)

    C = {tid: r for tid, r in load_arm(run_dir, "C").items() if tid in slice_ids}
    sl_keys = {tid: keys[tid] for tid in C if tid in keys}
    defect_ids = {tid for tid, k in sl_keys.items() if k.has_defect}

    # calibrate the gate on the DEFECT class only (blinding: clean labels unused)
    revs_by_task = {tid: rec.get("reviewers", []) for tid, rec in C.items()}
    gate = gate_from_defect_flags(revs_by_task, defect_ids, alpha=alpha)

    # baseline (no gate) vs gated
    base_verdicts = rebuild_verdicts(C, sl_keys, gate=None)
    gated_verdicts = rebuild_verdicts(C, sl_keys, gate=gate)
    base = score_arm("C-baseline", base_verdicts, sl_keys)
    gated = score_arm("C-conformal", gated_verdicts, sl_keys)

    # which tasks the gate abstained, split by defect/clean
    abst_fa, abst_catch = [], []
    for tid, v in gated_verdicts.items():
        if v.abstained:
            (abst_catch if sl_keys[tid].has_defect else abst_fa).append((tid, C[tid]["kind"]))

    print(f"\n===== CONFORMAL RE-SCORE: {which}, run={run_dir.name}, alpha={alpha}, "
          f"tau={gate.tau:.4f} =====")
    print(f"  scored: {base.n}  (defects {base.defects}, cleans {base.cleans})")
    print(f"  {'metric':22} {'baseline':>12} {'conformal':>12}")
    print(f"  {'caught-defect':22} {base.caught}/{base.defects}={base.caught_defect_rate!s:>7}"
          f"   {gated.caught}/{gated.defects}={gated.caught_defect_rate!s:>7}")
    print(f"  {'false-alarm':22} {base.false_alarms}/{base.cleans}={base.false_alarm_rate!s:>7}"
          f"   {gated.false_alarms}/{gated.cleans}={gated.false_alarm_rate!s:>7}")
    print(f"  {'agreement-soundness':22} {base.agreement_soundness!s:>12} {gated.agreement_soundness!s:>12}")
    print(f"  {'blended':22} {base.blended!s:>12} {gated.blended!s:>12}")
    print(f"  abstained: {gated.abstained}  (on defects {gated.abstained_on_defect}, on cleans "
          f"{gated.abstained - gated.abstained_on_defect})")
    print(f"  caught-defect CI95: baseline {base.caught_defect_ci}  conformal {gated.caught_defect_ci}")
    print(f"\n  abstained FALSE ALARMS ({len(abst_fa)}): {[t for t, _ in abst_fa]}")
    print(f"  abstained CATCHES  ({len(abst_catch)}): {[(t.split('__')[-1]) for t, _ in abst_catch]}")

    if "--emit" in sys.argv:
        out = run_dir / f"arm_C_conformal_{which}.jsonl"
        with out.open("w", encoding="utf-8") as fh:
            for tid, v in gated_verdicts.items():
                rec = {**v.to_dict(), "kind": C[tid]["kind"], "cost_usd": C[tid].get("cost_usd", 0.0),
                       "reviewers": C[tid].get("reviewers", [])}
                fh.write(json.dumps(rec) + "\n")
        print(f"\n  -> emitted gated verdicts to {out}")

    return {"baseline": base.to_dict(), "conformal": gated.to_dict(), "tau": gate.tau,
            "alpha": alpha, "abstained_fa": abst_fa, "abstained_catch": abst_catch}


if __name__ == "__main__":
    res = main()
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        Path(out).write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
        print(f"  -> {out}")
