"""Recover agy-unusable rows in a slice reviews file (agy is local/free).

The fresh re-run left agy degraded on some tasks (cold-daemon churn); Codex was
100% usable. This re-runs agy ONLY on the rows where agy is currently unusable,
with the SAME calibrated+method (_PLUS) prompt, keeping the existing Codex verdict.
Never touches Codex. Last-wins rewrite of the file.

Usage: python -m evals.precision_agy_recover <reviews.jsonl> [<reviews2.jsonl> ...]
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from overmind.benchmark.reviewers import REVIEW_INSTRUCTION_CALIBRATED_PLUS, BackendReviewer  # noqa: E402
from overmind.benchmark.tasks import load_tasks  # noqa: E402
from overmind.verification.judge_backends import AgyBackend  # noqa: E402

DATA = ROOT / "benchmark_data"


def main() -> int:
    tasks = {t.id: t for t in load_tasks(DATA / "tasks.json")}
    agy = BackendReviewer(AgyBackend(), vendor="agy", instruction=REVIEW_INSTRUCTION_CALIBRATED_PLUS)
    for path in sys.argv[1:]:
        p = Path(path)
        recs = []
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                recs.append(json.loads(line))
        todo = [r for r in recs if not r.get("agy", {}).get("usable", False)]
        print(f"[agy-recover] {p.name}: {len(todo)}/{len(recs)} agy-unusable to redo", flush=True)
        fixed = 0
        for r in recs:
            if r.get("agy", {}).get("usable", False):
                continue
            t = tasks.get(r["task_id"])
            if t is None:
                continue
            av = agy(t)
            r["agy"] = av.to_dict()
            r["agy_raw"] = (av.raw or "")[:200]
            fixed += int(av.usable)
        p.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
        now_usable = sum(1 for r in recs if r.get("agy", {}).get("usable", False))
        print(f"[agy-recover] {p.name}: agy usable now {now_usable}/{len(recs)} (recovered {fixed})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
