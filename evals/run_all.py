"""Single entrypoint for the Overmind/Sentinel measurement harness.

Runs all three held-out evals, writes per-eval JSON to ``evals/results/`` plus a
combined ``evals/results/summary.json``, and prints a tight scoreboard.

    python -m evals.run_all      # or:  make evals

Truth-first: scores are reported as measured. Exit code is always 0 — this is a
measurement run, not a gate; the numbers (good or bad) are the product.
"""
from __future__ import annotations

import json

from evals import judge_masterkey, memory_recall, quorum_decorrelation, specbench_style
from evals.common import RESULTS_DIR, seed_everything, write_result


def main() -> int:
    seed_everything()

    print("=" * 72)
    print("Overmind/Sentinel measurement harness -- held-out evals")
    print("=" * 72)

    sb = specbench_style.main()
    print("-" * 72)
    jm = judge_masterkey.main()
    print("-" * 72)
    mr = memory_recall.main()
    print("-" * 72)
    qd = quorum_decorrelation.main()
    print("=" * 72)

    summary = {
        "harness": "overmind-sentinel-measurement",
        "evals": {
            "specbench_style": {
                "validation_pass_rate": sb["validation_pass_rate"],
                "heldout_pass_rate": sb["heldout_pass_rate"],
                "specbench_gap": sb["specbench_gap"],
                "reward_hack_heldout_catch_rate": sb["reward_hack"]["heldout_catch_rate"],
                "visible_only_false_certifications": sb["reward_hack"]["visible_only_false_certifications"],
            },
            "judge_masterkey": {
                "degenerate_false_pass_rate": jm["degenerate"]["false_pass_rate"],
                "genuine_accuracy": jm["genuine"]["accuracy"],
                "injection_boundary_false_pass_rate": jm["injection_boundary"]["false_pass_rate"],
            },
            "memory_recall": {
                "recall": mr["recall"],
                "precision": mr["precision"],
                "stale_suppression_rate": mr["stale_suppression_rate"],
                "naive_stale_leak_rate": mr["naive_stale_leak_rate"],
                "expired_fact_suppressed": mr["expired_probe"]["expired_fact_suppressed"],
            },
            "quorum_decorrelation": {
                "overcount_rate_before": qd["correlated_panels"]["overcount_rate_before"],
                "overcount_rate_after": qd["correlated_panels"]["overcount_rate_after"],
                "honest_panels_unchanged_rate": qd["honest_panels"]["unchanged_rate"],
            },
        },
    }
    path = write_result("summary", summary)

    print("SCOREBOARD")
    print(json.dumps(summary["evals"], indent=2))
    print(f"\nResults dir: {RESULTS_DIR}")
    print(f"Summary:     {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
