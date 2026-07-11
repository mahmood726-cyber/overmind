"""Complete the credit-interrupted PLUS run WITHOUT burning Codex (out of credits).

The `--plus` run stopped mid-slice on a Codex credit-exhaustion guard (119/139 Codex
usable). agy (local, google family) is NOT credit-limited, so we can finish the agy
lane cleanly and construct a full-slice PLUS Arm-C number with an explicit,
CONSERVATIVE Codex fill for the credit-dead tasks:

  * agy: from the PLUS file if present+usable; otherwise run agy-PLUS live now (free).
  * codex: from the PLUS file if usable; otherwise FILL from the completed
    plain-calibrated run (reviews_CALIBRATED.jsonl, Codex 139/139 usable) and mark
    ``codex_fill=True``. The plain-calibrated Codex did NOT see the method criterion,
    so on the method_mismatch class it ACCEPTS — i.e. the fill under-detects the very
    defect PLUS is meant to recover, biasing the constructed number AGAINST the
    improvement. The reported PLUS recall is therefore a conservative LOWER BOUND.

Writes reviews_CALIBRATED_PLUS_COMPLETED.jsonl and prints how many rows were filled.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from overmind.benchmark.reviewers import (  # noqa: E402
    REVIEW_INSTRUCTION_CALIBRATED_PLUS, BackendReviewer)
from overmind.benchmark.tasks import held_out_ids, load_keys, load_tasks  # noqa: E402
from overmind.benchmark.witnesses import run_witness  # noqa: E402
from overmind.verification.judge_backends import AgyBackend  # noqa: E402

DATA = ROOT / "benchmark_data"
OUT = DATA / "runs_live_accuracy"


def _load(path: Path) -> dict:
    d = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                r = json.loads(line)
                d[r["task_id"]] = r
    return d


def main() -> int:
    tasks = load_tasks(DATA / "tasks.json")
    keys = load_keys(DATA / "keys" / "keys.json")
    ho = held_out_ids([t.id for t in tasks])
    held = sorted([t for t in tasks if t.id in ho], key=lambda t: t.id)
    plus = _load(OUT / "reviews_CALIBRATED_PLUS.jsonl")
    plain = _load(OUT / "reviews_CALIBRATED.jsonl")   # Codex 139/139 usable
    agy_rev = BackendReviewer(AgyBackend(), vendor="agy",
                              instruction=REVIEW_INSTRUCTION_CALIBRATED_PLUS)

    out_path = OUT / "reviews_CALIBRATED_PLUS_COMPLETED.jsonl"
    filled = agy_ran = 0
    with out_path.open("w", encoding="utf-8") as sink:
        for t in held:
            p = plus.get(t.id)
            wd = bool(run_witness(t).defect)
            # agy: use PLUS if usable, else run agy-PLUS live (free/local)
            if p and p.get("agy", {}).get("usable", False):
                agy = p["agy"]
            else:
                av = agy_rev(t); agy = av.to_dict(); agy_ran += 1
            # codex: use PLUS if usable, else fill from plain-calibrated (marked)
            codex_fill = False
            if p and p.get("codex", {}).get("usable", False):
                codex = p["codex"]
            else:
                codex = dict(plain[t.id]["codex"]); codex_fill = True; filled += 1
            rec = {"task_id": t.id, "codex": codex, "agy": agy, "witness_defect": wd,
                   "codex_fill": codex_fill}
            sink.write(json.dumps(rec) + "\n")
    n_cx_fill = filled
    print(f"[complete-plus] wrote {out_path.name}: {len(held)} rows; "
          f"agy_live_calls={agy_ran}; codex_filled_from_plain={n_cx_fill} (conservative, marked).")
    # how many filled rows are method_mismatch (the class PLUS targets)?
    mm_fill = sum(1 for t in held if keys[t.id].defect_type == "method_mismatch"
                  and not (plus.get(t.id, {}).get("codex", {}).get("usable", False)))
    print(f"[complete-plus] of the {n_cx_fill} Codex-filled, method_mismatch defects = {mm_fill} "
          f"(agy-PLUS carries these; plain Codex fill accepts them -> conservative).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
