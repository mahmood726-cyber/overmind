"""Two-slice promotion confirmation (AN-2): re-run the model arms A/B/C on the
SEALED FROZEN slice and check the held-out "C beats A and B" delta re-holds there.

A win on held-out alone is 'harness updating', not 'harness benefit'
(arXiv:2605.30621). This driver is the frozen half of the two-slice rule. It is
ADDITIVE — it does not modify the released `run_benchmark.py`; it reuses its
reviewer factories and the same runner/scorer, targeting the frozen slice.

Usage (Claude worker over SSH to the laptop subscription login):
    OVERMIND_CLAUDE_SSH_HOST=... OVERMIND_CLAUDE_SSH_KEY=... \
    python scripts/benchmark_frozen_confirm.py --max-tasks=40
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from overmind.benchmark.runner import ArmSpec, run_arm  # noqa: E402
from overmind.benchmark.scoring import evaluate_win_condition, score_arm  # noqa: E402
from overmind.benchmark.tasks import frozen_ids, load_keys, load_tasks  # noqa: E402
from overmind.reliability.checkpoint import CheckpointStore  # noqa: E402
from run_benchmark import _claude_backend, _live_vendors, _real_reviewer  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "benchmark_data"
OUT_DIR = DATA_DIR / "runs_frozen"


def main() -> int:
    max_tasks = next((int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--max-tasks=")), 40)
    tasks = load_tasks(DATA_DIR / "tasks.json")
    keys = load_keys(DATA_DIR / "keys" / "keys.json")
    fz = frozen_ids([t.id for t in tasks])
    frozen = sorted([t for t in tasks if t.id in fz], key=lambda t: t.id)[:max_tasks]
    fz_keys = {k: v for k, v in keys.items() if k in {t.id for t in frozen}}
    store = CheckpointStore(DATA_DIR / "checkpoints_frozen")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    live, notes = _live_vendors()
    print("live vendors:", sorted(live))
    a_vendor = "claude" if "claude" in live else next(iter(live), None)
    if a_vendor is None:
        print("NO live vendor — cannot run frozen confirmation"); return 1

    fam = {"claude": "anthropic", "codex": "openai", "gemini": "google", "agy": "google"}
    picked, seen = [], set()
    for v in live:
        if fam.get(v) not in seen:
            seen.add(fam.get(v)); picked.append(v)

    def run(name, reviewers, use_witness):
        r = run_arm(ArmSpec(name, reviewers, use_witness=use_witness), frozen,
                    checkpoint_store=store, results_path=OUT_DIR / f"arm_{name}.jsonl",
                    cost_fn=lambda t, v: 0.0)
        m = score_arm(name, r.verdicts, fz_keys)
        print(f"  Arm {name}: status={'VALID' if r.valid else 'INVALID'} usable={r.usable_rate} "
              f"caught={m.caught_defect_rate} FAR={m.false_alarm_rate} agree={m.agreement_soundness}")
        return m, r.valid

    print(f"FROZEN confirmation on {len(frozen)} sealed tasks "
          f"(defects={sum(1 for k in fz_keys.values() if k.has_defect)}, "
          f"clean={sum(1 for k in fz_keys.values() if not k.has_defect)}); reviewers picked={picked}")
    a_m, a_ok = run("A", [_real_reviewer(a_vendor)], False)
    b_m, b_ok = run("B", [_real_reviewer(a_vendor) for _ in range(3)], False)
    if len(picked) >= 2:
        c_m, c_ok = run("C", [_real_reviewer(v) for v in picked], True)
    else:
        print("  Arm C STAGED (need >=2 distinct families)"); return 1

    win = evaluate_win_condition(a_m, b_m, c_m).to_dict() if (a_ok and b_ok and c_ok) else None
    out = {"slice": "FROZEN", "n": len(frozen), "picked": picked,
           "arms": {"A": a_m.to_dict(), "B": b_m.to_dict(), "C": c_m.to_dict()},
           "valid": {"A": a_ok, "B": b_ok, "C": c_ok}, "win_condition": win, "notes": notes}
    (OUT_DIR / "frozen_scorecard.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("FROZEN win condition:", (win or {}).get("verdict", "N/A (an arm invalid)"))
    print("scorecard ->", OUT_DIR / "frozen_scorecard.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
