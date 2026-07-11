"""PRECISION RE-EVAL driver (feature branch, measurement-only) — Fix #1 + #3 data.

Re-runs the SAME live heterogeneous panel (Codex-SSH openai + agy google + the
deterministic witness floor) over the SAME sealed held-out slice, but with the
CALIBRATED reviewer prompt (``REVIEW_INSTRUCTION_CALIBRATED``): (1) a non-significant
CI is not a defect, (2) each flag carries an emitted confidence. Writes a NEW jsonl
so the baseline is preserved for before/after. Everything else — panel, parser,
witness, scorer — is the harness's own code.

Resumable + mid-run Codex credit-exhaustion guard (stop, never emit a degraded
number), mirroring live_vendor_accuracy. Scoring is done separately by
``evals.precision_measure`` so the SAME scorer produces baseline and re-eval numbers.

Usage:
    python -m evals.precision_reeval                 # both vendors, full slice
    python -m evals.precision_reeval --agy-only      # re-run agy only (hold Codex baseline)
    python -m evals.precision_reeval --spot=N         # first N tasks only (Codex spot-check)
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from overmind.benchmark.reviewers import (  # noqa: E402
    REVIEW_INSTRUCTION_CALIBRATED, REVIEW_INSTRUCTION_CALIBRATED_PLUS,
    BackendReviewer, ReviewerVerdict,
)
from overmind.benchmark.tasks import held_out_ids, load_keys, load_tasks  # noqa: E402
from overmind.benchmark.witnesses import run_witness  # noqa: E402
from overmind.verification.judge_backends import AgyBackend  # noqa: E402
from evals.live_vendor_accuracy import SshCodexBackend  # noqa: E402

DATA = ROOT / "benchmark_data"
OUT = DATA / "runs_live_accuracy"
BASELINE = OUT / "reviews_BASELINE.jsonl"
CREDITS_DEAD = threading.Event()
MAX_WORKERS = 4


def _load_done(path: Path) -> dict:
    done = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                done[rec["task_id"]] = rec
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def _collect(task, codex_rev, agy_rev):
    if CREDITS_DEAD.is_set():
        return task.id, ReviewerVerdict(flag=False, vendor="codex", usable=False,
                                        raw="SKIPPED: credits dead"), None, bool(run_witness(task).defect)
    cv = codex_rev(task)
    if "out of credits" in (cv.raw or "").lower():
        CREDITS_DEAD.set()
    av = agy_rev(task)
    wd = bool(run_witness(task).defect)
    return task.id, cv, av, wd


def main() -> int:
    spot = next((int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--spot=")), None)
    agy_only = "--agy-only" in sys.argv
    use_plus = "--plus" in sys.argv
    instruction = REVIEW_INSTRUCTION_CALIBRATED_PLUS if use_plus else REVIEW_INSTRUCTION_CALIBRATED
    tasks = load_tasks(DATA / "tasks.json")
    keys = load_keys(DATA / "keys" / "keys.json")
    ho = held_out_ids([t.id for t in tasks])
    held = sorted([t for t in tasks if t.id in ho], key=lambda t: t.id)
    if spot is not None:
        held = held[:spot]
    ho_keys = {t.id: keys[t.id] for t in held if t.id in keys}
    OUT.mkdir(parents=True, exist_ok=True)
    suffix = f"_spot{spot}" if spot else ("_AGYONLY" if agy_only else ("_PLUS" if use_plus else ""))
    jsonl = OUT / f"reviews_CALIBRATED{suffix}.jsonl"

    codex_rev = BackendReviewer(SshCodexBackend(), vendor="codex", instruction=instruction)
    agy_rev = BackendReviewer(AgyBackend(), vendor="agy", instruction=instruction)

    done = _load_done(jsonl)
    baseline = _load_done(BASELINE)

    if agy_only:
        # re-run agy with the calibrated prompt; hold Codex at its BASELINE verdict.
        todo = [t for t in held if t.id not in done]
        print(f"[precision-reeval agy-only] {len(todo)} tasks (Codex held at baseline)", flush=True)
        with jsonl.open("a", encoding="utf-8") as sink:
            for t in todo:
                av = agy_rev(t)
                base = baseline.get(t.id, {})
                rec = {"task_id": t.id, "codex": base.get("codex", {"flag": False, "usable": False}),
                       "agy": av.to_dict(), "witness_defect": bool(run_witness(t).defect),
                       "codex_raw": base.get("codex_raw", ""), "agy_raw": (av.raw or "")[:200]}
                sink.write(json.dumps(rec) + "\n"); sink.flush()
        print(f"[precision-reeval agy-only] wrote {jsonl}", flush=True)
        return 0

    def _needs(t):
        r = done.get(t.id)
        return r is None or not bool(r.get("codex", {}).get("usable", True))
    todo = [t for t in held if _needs(t)]
    n_def = sum(1 for t in held if ho_keys[t.id].has_defect)
    print(f"[precision-reeval] held-out n={len(held)} (defects={n_def}, clean={len(held)-n_def}); "
          f"done={len(done)}, todo={len(todo)}; CALIBRATED prompt, both vendors", flush=True)

    t0 = time.time()
    with jsonl.open("a", encoding="utf-8") as sink, ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(_collect, t, codex_rev, agy_rev): t for t in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            tid, cv, av, wd = fut.result()
            if av is None:
                continue
            rec = {"task_id": tid, "codex": cv.to_dict(), "agy": av.to_dict(),
                   "witness_defect": wd, "codex_raw": (cv.raw or "")[:200], "agy_raw": (av.raw or "")[:200]}
            sink.write(json.dumps(rec) + "\n"); sink.flush()
            if i % 10 == 0 or i == len(todo):
                fl = " [CREDITS DEAD-draining]" if CREDITS_DEAD.is_set() else ""
                print(f"[precision-reeval] {len(done)+i}/{len(held)} ({round(time.time()-t0)}s){fl}", flush=True)

    if CREDITS_DEAD.is_set():
        recs = _load_done(jsonl)
        cu = sum(1 for r in recs.values() if r.get("codex", {}).get("usable"))
        print(f"\n#### CREDIT EXHAUSTION MID-RUN — STOPPED. Codex usable {cu}/{len(held)}. INCOMPLETE, "
              f"NOT a clean number. Resume with `python -m evals.precision_reeval`. No score emitted.",
              flush=True)
        return 2

    recs = _load_done(jsonl)
    cu = sum(1 for r in recs.values() if r.get("codex", {}).get("usable"))
    au = sum(1 for r in recs.values() if r.get("agy", {}).get("usable"))
    print(f"\n[precision-reeval] DONE. wrote {jsonl}  codex_usable={cu}/{len(held)} agy_usable={au}/{len(held)}",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
