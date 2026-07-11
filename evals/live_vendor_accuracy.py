"""LIVE-VENDOR ACCURACY driver (measurement-only, feature branch).

Produces a REAL live-vendor accuracy number for the harness's verification path
over the SEALED held-out slice of the MADE-style A/B/C benchmark, using a live
heterogeneous panel: Codex mahmood726 (laptop, SSH; openai family) + agy
flash_lite (local; google family) + the deterministic objective witness floor.

IMPORTANT — no harness behaviour is changed. The accuracy is computed entirely by
the harness's OWN code:
  * reviewer prompt + parser  -> overmind.benchmark.reviewers.BackendReviewer
  * aggregation (A / C / floor)-> overmind.benchmark.arms.arm_a / arm_c
  * objective witness          -> overmind.benchmark.witnesses.run_witness
  * scoring (recall/FPR + CI)  -> overmind.benchmark.scoring.score_arm
  * conformal accept/abstain   -> overmind.benchmark.conformal.gate_from_defect_flags
The ONLY new code is SshCodexBackend — a measurement transport wrapper that runs
the same `codex exec --sandbox read-only -` the local CodexBackend runs, but on
the laptop over SSH. Answer keys are read ONLY by the scorer (blinding preserved).

Usage:
    python -m evals.live_vendor_accuracy --max-tasks=N   # subset (first-N by id)
    python -m evals.live_vendor_accuracy                 # full held-out slice
Resumable: per-task reviewer verdicts are appended to a JSONL; a re-run skips
completed tasks. Run in background for the full slice (~20-30 min).
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from overmind.benchmark.arms import arm_a, arm_c  # noqa: E402
from overmind.benchmark.reviewers import BackendReviewer  # noqa: E402
from overmind.benchmark.scoring import score_arm  # noqa: E402
from overmind.benchmark.tasks import held_out_ids, load_keys, load_tasks  # noqa: E402
from overmind.benchmark.witnesses import run_witness  # noqa: E402
from overmind.verification.judge_backends import AgyBackend  # noqa: E402

DATA = ROOT / "benchmark_data"
OUT = DATA / "runs_live_accuracy"
KEY = r"C:\Users\mahmo\.ssh\node2_ed25519"
LAPTOP = "mahmo@100.80.183.43"
CODEX_EFFORT = "medium"   # stated in the report; conservative vs harness default xhigh
MAX_WORKERS = 4


class SshCodexBackend:
    """Measurement transport: `codex exec --sandbox read-only -` on the laptop over
    SSH, prompt on stdin. Mirrors overmind.verification.judge_backends.CodexBackend
    but remote. Returns stdout (the model answer; codex's verbose envelope goes to
    stderr). On any failure returns a JUDGE_ERROR string so the harness parser marks
    it unusable (never a silent flag=False)."""

    def __init__(self, effort: str = CODEX_EFFORT, timeout: int = 150):
        self.effort = effort
        self.timeout = timeout

    def query(self, prompt: str) -> str:
        remote = ('set "CODEX_HOME=%USERPROFILE%\\.codex" && '
                  "codex exec --skip-git-repo-check --sandbox read-only "
                  f"--config model_reasoning_effort={self.effort} -")
        argv = ["ssh", "-i", KEY, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                "-o", "StrictHostKeyChecking=accept-new", LAPTOP, remote]
        try:
            # Send UTF-8 BYTES explicitly (text=False): the Windows default (cp1252)
            # mangles non-ASCII artifact chars (+/-, <=, en-dash) so codex reads
            # "input is not valid UTF-8" and fails. Decode stdout as UTF-8 too.
            p = subprocess.run(argv, input=prompt.encode("utf-8"), capture_output=True,
                               timeout=self.timeout)
        except Exception as exc:  # noqa: BLE001
            return f"JUDGE_ERROR: ssh/codex exec failed: {exc}"
        out = (p.stdout or b"").decode("utf-8", errors="replace")
        err = (p.stderr or b"").decode("utf-8", errors="replace")
        if p.returncode != 0:
            return f"JUDGE_ERROR: codex rc={p.returncode}: {err[-160:]}"
        return out or "JUDGE_ERROR: empty stdout"


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
    """One task -> (task_id, codex_verdict_dict, agy_verdict_dict, witness_defect).
    Uses the harness's real BackendReviewer (real prompt + real parser)."""
    cv = codex_rev(task)
    av = agy_rev(task)
    wd = bool(run_witness(task).defect)
    return task.id, cv, av, wd


def main() -> int:
    max_tasks = next((int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--max-tasks=")), None)
    tasks = load_tasks(DATA / "tasks.json")
    keys = load_keys(DATA / "keys" / "keys.json")
    ho = held_out_ids([t.id for t in tasks])
    held = sorted([t for t in tasks if t.id in ho], key=lambda t: t.id)
    if max_tasks is not None:
        held = held[:max_tasks]
    ho_keys = {t.id: keys[t.id] for t in held if t.id in keys}
    OUT.mkdir(parents=True, exist_ok=True)
    jsonl = OUT / f"reviews{'_sub' + str(max_tasks) if max_tasks else ''}.jsonl"

    codex_rev = BackendReviewer(SshCodexBackend(), vendor="codex")
    agy_rev = BackendReviewer(AgyBackend(), vendor="agy")

    done = _load_done(jsonl)
    todo = [t for t in held if t.id not in done]
    n_def = sum(1 for t in held if ho_keys[t.id].has_defect)
    n_cln = len(held) - n_def
    print(f"[live-accuracy] held-out n={len(held)} (defects={n_def}, clean={n_cln}); "
          f"already done={len(done)}, todo={len(todo)}; codex_effort={CODEX_EFFORT}", flush=True)

    t_start = time.time()
    with jsonl.open("a", encoding="utf-8") as sink, ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(_collect, t, codex_rev, agy_rev): t for t in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            tid, cv, av, wd = fut.result()
            rec = {"task_id": tid, "codex": cv.to_dict(), "agy": av.to_dict(), "witness_defect": wd,
                   "codex_raw": (cv.raw or "")[:200], "agy_raw": (av.raw or "")[:200]}
            sink.write(json.dumps(rec) + "\n"); sink.flush()
            if i % 10 == 0 or i == len(todo):
                el = round(time.time() - t_start)
                print(f"[live-accuracy] {len(done)+i}/{len(held)} done ({el}s elapsed)", flush=True)

    # ---- everything below is deterministic; uses the harness's real code ----
    from overmind.benchmark.reviewers import ReviewerVerdict
    recs = _load_done(jsonl)

    def rv(d):
        return ReviewerVerdict(flag=bool(d["flag"]), reason=d.get("reason", ""), value=d.get("value"),
                               vendor=d.get("vendor", ""), usable=bool(d.get("usable", True)))

    a_verdicts, c_verdicts, ref_verdicts = {}, {}, {}
    c_reviewer_records = {}
    codex_usable = agy_usable = 0
    for t in held:
        r = recs.get(t.id)
        if r is None:
            continue
        cv, av, wd = rv(r["codex"]), rv(r["agy"]), bool(r["witness_defect"])
        codex_usable += int(cv.usable); agy_usable += int(av.usable)
        a_verdicts[t.id] = arm_a(t.id, [cv])                     # single-vendor (Codex)
        c_verdicts[t.id] = arm_c(t.id, [cv, av], wd)             # heterogeneous + floor
        ref_verdicts[t.id] = arm_c(t.id, [], wd)                # witness-only floor
        c_reviewer_records[t.id] = [cv.to_dict(), av.to_dict()]

    n = len(a_verdicts)
    a_m = score_arm("A (single Codex)", a_verdicts, ho_keys)
    c_m = score_arm("C (Codex+agy+floor)", c_verdicts, ho_keys)
    ref_m = score_arm("objective-ref (witness-only)", ref_verdicts, ho_keys)

    # conformal-gated Arm C (harness's real gate; addresses the FAR clause)
    from overmind.benchmark.conformal import gate_from_defect_flags
    from overmind.benchmark.arms import arm_c as _arm_c
    import os
    alpha = float(os.environ.get("OVERMIND_CONFORMAL_ALPHA", "0.10"))
    defect_ids = {tid for tid, k in ho_keys.items() if k.has_defect and tid in c_verdicts}
    gate = gate_from_defect_flags(c_reviewer_records, defect_ids, alpha=alpha)
    cg_verdicts = {tid: _arm_c(tid, [rv(r) for r in c_reviewer_records[tid]],
                              bool(c_verdicts[tid].witness_defect), gate=gate)
                   for tid in c_verdicts}
    cg_m = score_arm("C conformal", cg_verdicts, ho_keys)

    out = {
        "slice": "held_out", "n": n, "defects": a_m.defects, "cleans": a_m.cleans,
        "codex_usable_rate": round(codex_usable / max(n, 1), 4),
        "agy_usable_rate": round(agy_usable / max(n, 1), 4),
        "codex_effort": CODEX_EFFORT, "conformal_alpha": alpha,
        "arms": {m.arm: m.to_dict() for m in (a_m, c_m, ref_m, cg_m)},
    }
    (OUT / f"scorecard{'_sub' + str(max_tasks) if max_tasks else ''}.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    print("\n==== LIVE-VENDOR ACCURACY (held-out n={}) ====".format(n))
    for m in (ref_m, a_m, c_m, cg_m):
        print(f"  {m.arm:28} caught={m.caught_defect_rate} CI{m.caught_defect_ci} "
              f"| FAR={m.false_alarm_rate} CI{m.false_alarm_ci} "
              f"| caught={m.caught}/{m.defects} FA={m.false_alarms}/{m.cleans}")
    print(f"  usable: codex={out['codex_usable_rate']} agy={out['agy_usable_rate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
