"""CLI: run the public memory-recall benchmark and emit JSON + a headline line.

Examples
--------
  python -m evals.public_memory_bench.run_bench \
      --dataset locomo --data /path/to/locomo10.json --config fts

  python -m evals.public_memory_bench.run_bench \
      --dataset longmemeval --data /path/to/longmemeval_s.json \
      --config hybrid --limit 200

Data is NOT vendored (LoCoMo ~3MB CC-BY-NC; LongMemEval_s ~266MB). Download:
  LoCoMo:       https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json
  LongMemEval:  https://huggingface.co/datasets/xiaowu0162/longmemeval  (file: longmemeval_s)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.public_memory_bench.adapter import (
    load_locomo,
    load_longmemeval,
    run_recall,
)


def main() -> dict:
    ap = argparse.ArgumentParser(description="Public memory-recall benchmark (read-only).")
    ap.add_argument("--dataset", required=True, choices=["locomo", "longmemeval"])
    ap.add_argument("--data", required=True, help="Path to the dataset JSON file.")
    ap.add_argument("--config", default="fts", choices=["fts", "hybrid", "semantic"])
    ap.add_argument("--ks", default="1,3,5,10", help="Comma-separated k values.")
    ap.add_argument("--limit", type=int, default=0, help="Cap #samples (0 = all). Documented subset.")
    ap.add_argument("--out", default="", help="Write result JSON to this path.")
    args = ap.parse_args()

    ks = tuple(int(x) for x in args.ks.split(","))

    if args.dataset == "locomo":
        samples = load_locomo(args.data)
        gran = "turn"
    else:
        samples = load_longmemeval(args.data)
        gran = "session"

    subset_note = ""
    if args.limit and args.limit < len(samples):
        samples = samples[: args.limit]
        subset_note = f"documented subset: first {args.limit} samples of the full set"

    result = run_recall(
        samples,
        dataset=args.dataset,
        config=args.config,
        unit_granularity=gran,
        ks=ks,
        notes=subset_note,
    )

    payload = result.to_dict()
    print(json.dumps(payload, indent=2))
    line = " ".join(f"R@{k}={result.recall_at_k[k]:.1%}" for k in ks)
    print(
        f"[{args.dataset}/{args.config}/{gran}] {line} "
        f"| n={result.n_questions} samples={result.n_samples} "
        f"units={result.n_units_total} emb_backend={result.embedding_backend_available} "
        f"excluded_no_gold={result.excluded_no_gold}"
    )
    if args.out:
        Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"[wrote] {args.out}")
    return payload


if __name__ == "__main__":
    main()
