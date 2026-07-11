"""OFFLINE LOCAL-LLM ACCURACY driver (measurement-only, feature branch).

Answers the manifesto's "runs for a scientist on a laptop in Uganda" claim with
NUMBERS: run the harness's REAL verification path over the SEALED slices using
*local, CPU-only, quantized* models as the reviewer arms (via the harness's own
``LocalModelBackend`` -> Ollama ``/api/generate``) + the deterministic objective
witness floor. Compare to the live frontier panel (Codex+agy, 0.9524 / FAR 0.030).

IMPORTANT — no harness behaviour is changed. Accuracy is computed entirely by the
harness's OWN code:
  * local reviewer backend  -> overmind.verification.judge_backends.LocalModelBackend
  * reviewer prompt+parser  -> overmind.benchmark.reviewers.BackendReviewer
  * aggregation (A/C/floor) -> overmind.benchmark.arms.arm_a / arm_c
  * objective witness       -> overmind.benchmark.witnesses.run_witness
  * scoring (recall/FPR+CI) -> overmind.benchmark.scoring.score_arm
The ONLY new code is a thin timing/RAM wrapper (pure measurement — forwards the
prompt byte-for-byte) and the decorrelation math. Answer keys are read ONLY by the
scorer (blinding preserved). Runs models SEQUENTIALLY (one resident at a time) to
hold peak RAM inside a field-laptop envelope; CPU-only is enforced by the server
(OLLAMA_NUM_GPU=0, no GPU present).

Usage:
    python -m evals.offline_local_accuracy --collect               # run all models x both slices (resumable)
    python -m evals.offline_local_accuracy --collect --models=qwen --slices=held_out --max-tasks=5
    python -m evals.offline_local_accuracy --score                 # score + decorrelation from the JSONL
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from overmind.benchmark.arms import arm_a, arm_c  # noqa: E402
from overmind.benchmark.reviewers import BackendReviewer, ReviewerVerdict  # noqa: E402
from overmind.benchmark.scoring import score_arm, wilson_ci  # noqa: E402
from overmind.benchmark.tasks import frozen_ids, held_out_ids, load_keys, load_tasks  # noqa: E402
from overmind.benchmark.witnesses import run_witness  # noqa: E402
from overmind.verification.judge_backends import LocalModelBackend  # noqa: E402

DATA = ROOT / "benchmark_data"
OUT = DATA / "runs_offline_local"
JSONL = OUT / "reviews_offline.jsonl"

# Model registry: label -> ollama tag. Different ARCHITECTURES on purpose
# (decorrelation is the whole point): Alibaba Qwen2.5, Meta Llama-3.1, MS Phi-3.
MODELS = {
    "qwen":  "qwen2.5:7b-instruct-q4_K_M",
    "llama": "llama3.1:8b-instruct-q4_K_M",
    "phi":   "phi3:mini",
}
SLICES = {"held_out": held_out_ids, "frozen": frozen_ids}


class TimedBackend:
    """Pure-measurement wrapper: times ``query`` and forwards the prompt verbatim
    to the wrapped harness backend. Records last latency in ``.last_s``."""

    def __init__(self, backend):
        self.backend = backend
        self.last_s = 0.0

    def query(self, prompt: str) -> str:
        t0 = time.time()
        out = self.backend.query(prompt)
        self.last_s = time.time() - t0
        return out


class RamSampler(threading.Thread):
    """Sample summed RSS of all 'ollama' processes; track the high-water mark (GB)."""

    def __init__(self, interval: float = 1.0):
        super().__init__(daemon=True)
        self.interval = interval
        self.peak_gb = 0.0
        self._stop = threading.Event()

    def run(self):
        try:
            import psutil
        except ImportError:
            return
        while not self._stop.is_set():
            total = 0
            for p in psutil.process_iter(["name", "memory_info"]):
                try:
                    if "ollama" in (p.info["name"] or "").lower():
                        total += p.info["memory_info"].rss
                except Exception:  # noqa: BLE001
                    continue
            self.peak_gb = max(self.peak_gb, total / 1e9)
            self._stop.wait(self.interval)

    def stop(self):
        self._stop.set()


def _slice_tasks(slice_name: str, tasks):
    ids = SLICES[slice_name]([t.id for t in tasks])
    return sorted([t for t in tasks if t.id in ids], key=lambda t: t.id)


def _load_done() -> dict:
    """(slice, model, task_id) -> record."""
    done = {}
    if JSONL.exists():
        for line in JSONL.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                done[(r["slice"], r["model"], r["task_id"])] = r
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def collect() -> int:
    which_models = _arg_list("--models", default=list(MODELS))
    which_slices = _arg_list("--slices", default=list(SLICES))
    max_tasks = _arg_int("--max-tasks")
    tasks = load_tasks(DATA / "tasks.json")
    keys = load_keys(DATA / "keys" / "keys.json")
    OUT.mkdir(parents=True, exist_ok=True)
    done = _load_done()

    # Warm the deterministic witness once per task (kind-agnostic, model-free).
    for slice_name in which_slices:
        held = _slice_tasks(slice_name, tasks)
        if max_tasks:
            held = held[:max_tasks]
        ndef = sum(1 for t in held if keys[t.id].has_defect)
        print(f"\n#### SLICE {slice_name}: n={len(held)} defects={ndef} clean={len(held)-ndef}", flush=True)
        # SEQUENTIAL over models — one model resident at a time (RAM discipline).
        for mlabel in which_models:
            tag = MODELS[mlabel]
            backend = TimedBackend(LocalModelBackend(model=tag, enabled=True, timeout=600))
            reviewer = BackendReviewer(backend, vendor=mlabel)
            todo = [t for t in held if (slice_name, mlabel, t.id) not in done
                    or not bool(done[(slice_name, mlabel, t.id)].get("usable", True))]
            print(f"  [{mlabel}={tag}] todo={len(todo)}/{len(held)}", flush=True)
            if not todo:
                continue
            sampler = RamSampler(); sampler.start()
            t_start = time.time(); lat = []
            with JSONL.open("a", encoding="utf-8") as sink:
                for i, t in enumerate(todo, 1):
                    v = reviewer(t)
                    wd = bool(run_witness(t).defect)
                    rec = {"slice": slice_name, "model": mlabel, "tag": tag, "task_id": t.id,
                           "flag": v.flag, "reason": v.reason[:200], "value": v.value,
                           "vendor": v.vendor, "usable": v.usable, "witness_defect": wd,
                           "latency_s": round(backend.last_s, 2), "raw_head": (v.raw or "")[:200]}
                    sink.write(json.dumps(rec) + "\n"); sink.flush()
                    lat.append(backend.last_s)
                    if i % 5 == 0 or i == len(todo):
                        el = round(time.time() - t_start)
                        med = sorted(lat)[len(lat)//2]
                        print(f"    {i}/{len(todo)} done | {el}s elapsed | median {med:.1f}s/task "
                              f"| RAM peak {sampler.peak_gb:.2f}GB | last flag={v.flag} usable={v.usable}",
                              flush=True)
            sampler.stop()
            # per-model timing/RAM summary line
            lat_sorted = sorted(lat)
            summ = {"slice": slice_name, "model": mlabel, "tag": tag, "kind": "_timing_summary",
                    "n": len(lat), "total_s": round(sum(lat), 1),
                    "median_s": round(lat_sorted[len(lat_sorted)//2], 2) if lat else None,
                    "p90_s": round(lat_sorted[int(len(lat_sorted)*0.9)], 2) if lat else None,
                    "max_s": round(max(lat), 2) if lat else None,
                    "ram_peak_gb": round(sampler.peak_gb, 2)}
            with (OUT / "timing.jsonl").open("a", encoding="utf-8") as tf:
                tf.write(json.dumps(summ) + "\n")
            print(f"  [{mlabel}] TIMING {summ}", flush=True)
    print("\ncollection complete. Score with: python -m evals.offline_local_accuracy --score", flush=True)
    return 0


# ----------------------------- scoring + decorrelation -----------------------------

def _rv(r) -> ReviewerVerdict:
    return ReviewerVerdict(flag=bool(r["flag"]), reason=r.get("reason", ""), value=r.get("value"),
                           vendor=r.get("model", r.get("vendor", "")), usable=bool(r.get("usable", True)))


def _co_failure(miss_a: set, miss_b: set, universe: set) -> dict:
    """Co-failure stats on a set (defects for co-miss, cleans for co-FA).
    Reports observed joint-failure rate vs the independence prediction."""
    n = len(universe)
    a, b = len(miss_a), len(miss_b)
    both = len(miss_a & miss_b)
    pa, pb = (a / n if n else 0.0), (b / n if n else 0.0)
    indep = pa * pb
    obs = both / n if n else 0.0
    # correlation of the two 0/1 failure vectors (phi coefficient)
    only_a = len(miss_a - miss_b); only_b = len(miss_b - miss_a)
    neither = n - both - only_a - only_b
    import math
    num = both * neither - only_a * only_b
    den = math.sqrt((both + only_a) * (both + only_b) * (neither + only_a) * (neither + only_b))
    phi = round(num / den, 4) if den else None
    return {"n": n, "fail_a": a, "fail_b": b, "both_fail": both,
            "p_a": round(pa, 4), "p_b": round(pb, 4),
            "obs_joint": round(obs, 4), "indep_joint": round(indep, 4),
            "excess_over_indep": round(obs - indep, 4), "phi": phi}


def score() -> int:
    tasks = load_tasks(DATA / "tasks.json")
    keys = load_keys(DATA / "keys" / "keys.json")
    done = _load_done()
    report = {"generated": "offline_local_accuracy", "slices": {}}

    for slice_name in SLICES:
        held = _slice_tasks(slice_name, tasks)
        if not held:
            continue
        held_ids = [t.id for t in held]
        sk = {tid: keys[tid] for tid in held_ids}
        defect_ids = {tid for tid in held_ids if keys[tid].has_defect}
        clean_ids = {tid for tid in held_ids if not keys[tid].has_defect}
        # which models actually have data for this slice
        models_here = [m for m in MODELS if any((slice_name, m, tid) in done for tid in held_ids)]
        if not models_here:
            continue
        wd = {tid: bool(next((done[(slice_name, m, tid)]["witness_defect"]
                              for m in models_here if (slice_name, m, tid) in done), False))
              for tid in held_ids}

        arms = {}
        # objective-ref floor alone
        ref = {tid: arm_c(tid, [], wd[tid]) for tid in held_ids}
        arms["objective_floor"] = score_arm("objective_floor", ref, sk).to_dict()

        # per-model: alone (arm_a) and model+floor (arm_c single reviewer)
        per_model_verdicts = {}
        usable_rate = {}
        for m in models_here:
            recs = {tid: done.get((slice_name, m, tid)) for tid in held_ids}
            recs = {tid: r for tid, r in recs.items() if r is not None}
            per_model_verdicts[m] = recs
            usable_rate[m] = round(sum(1 for r in recs.values() if r.get("usable", True)) / max(len(recs), 1), 4)
            a = {tid: arm_a(tid, [_rv(r)]) for tid, r in recs.items()}
            c = {tid: arm_c(tid, [_rv(r)], wd[tid]) for tid, r in recs.items()}
            arms[f"{m}_alone"] = score_arm(f"{m}_alone", a, sk).to_dict()
            arms[f"{m}+floor"] = score_arm(f"{m}+floor", c, sk).to_dict()

        # 2-model panels + floor (arm_c heterogeneous). All pairs.
        import itertools
        pairs = list(itertools.combinations(models_here, 2))
        for m1, m2 in pairs:
            common = [tid for tid in held_ids
                      if (slice_name, m1, tid) in done and (slice_name, m2, tid) in done]
            c = {tid: arm_c(tid, [_rv(done[(slice_name, m1, tid)]), _rv(done[(slice_name, m2, tid)])], wd[tid])
                 for tid in common}
            arms[f"{m1}+{m2}+floor"] = score_arm(f"{m1}+{m2}+floor", c, sk).to_dict()

        # 3-model panel + floor if all present
        if len(models_here) >= 3:
            common = [tid for tid in held_ids if all((slice_name, m, tid) in done for m in models_here)]
            c = {tid: arm_c(tid, [_rv(done[(slice_name, m, tid)]) for m in models_here], wd[tid])
                 for tid in common}
            arms["+".join(models_here) + "+floor"] = score_arm("all+floor", c, sk).to_dict()

        # ---- decorrelation: co-miss on defects, co-FA on cleans (per model pair) ----
        # A model "misses" a defect if it did NOT flag it; "false-alarms" on a clean if it flagged.
        # Note: the objective floor catches witness-detectable defects regardless of the model,
        # so co-miss is reported on REVIEWER-ONLY defects (where the model must earn it) AND on
        # all defects. False alarms are reviewer-driven by construction (floor never flags cleans).
        reviewer_only_def = {tid for tid in defect_ids if not wd[tid]}
        def missed(m, idset):
            rs = per_model_verdicts[m]
            return {tid for tid in idset if tid in rs and not _rv(rs[tid]).flag}
        def falsed(m, idset):
            rs = per_model_verdicts[m]
            return {tid for tid in idset if tid in rs and _rv(rs[tid]).flag}
        decorr = {}
        for m1, m2 in pairs:
            decorr[f"{m1}|{m2}"] = {
                "co_miss_all_defects": _co_failure(missed(m1, defect_ids), missed(m2, defect_ids), defect_ids),
                "co_miss_reviewer_only": _co_failure(missed(m1, reviewer_only_def), missed(m2, reviewer_only_def), reviewer_only_def),
                "co_false_alarm_cleans": _co_failure(falsed(m1, clean_ids), falsed(m2, clean_ids), clean_ids),
            }

        report["slices"][slice_name] = {
            "n": len(held), "defects": len(defect_ids), "cleans": len(clean_ids),
            "reviewer_only_defects": len(reviewer_only_def),
            "usable_rate": usable_rate, "arms": arms, "decorrelation": decorr,
        }

    # ---- frontier co-failure for comparison (from the live baseline reviews) ----
    report["frontier_comparison"] = _frontier_decorrelation(tasks, keys)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "offline_scorecard.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    _print_report(report)
    print(f"\nscorecard -> {OUT / 'offline_scorecard.json'}")
    return 0


def _frontier_decorrelation(tasks, keys) -> dict:
    """Codex-vs-agy co-failure on the held-out slice, from the live baseline reviews
    (benchmark_data/runs_live_accuracy). Same definitions as the local decorrelation
    so the two are directly comparable."""
    src = None
    for cand in ("reviews_BASELINE.jsonl", "reviews.jsonl"):
        p = DATA / "runs_live_accuracy" / cand
        if p.exists():
            src = p; break
    if src is None:
        return {"note": "no live baseline reviews found for frontier comparison"}
    recs = {}
    for line in src.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
            recs[r["task_id"]] = r
        except (json.JSONDecodeError, KeyError):
            continue
    held = _slice_tasks("held_out", tasks)
    ids = [t.id for t in held if t.id in recs]
    defect_ids = {tid for tid in ids if keys[tid].has_defect}
    clean_ids = {tid for tid in ids if not keys[tid].has_defect}
    wd = {tid: bool(recs[tid].get("witness_defect")) for tid in ids}
    reviewer_only_def = {tid for tid in defect_ids if not wd[tid]}

    def codex_flag(tid): return bool(recs[tid]["codex"]["flag"])
    def agy_flag(tid): return bool(recs[tid]["agy"]["flag"])
    codex_miss = {tid for tid in defect_ids if not codex_flag(tid)}
    agy_miss = {tid for tid in defect_ids if not agy_flag(tid)}
    codex_miss_ro = {tid for tid in reviewer_only_def if not codex_flag(tid)}
    agy_miss_ro = {tid for tid in reviewer_only_def if not agy_flag(tid)}
    codex_fa = {tid for tid in clean_ids if codex_flag(tid)}
    agy_fa = {tid for tid in clean_ids if agy_flag(tid)}
    return {
        "source": src.name, "slice": "held_out", "pair": "codex|agy",
        "co_miss_all_defects": _co_failure(codex_miss, agy_miss, defect_ids),
        "co_miss_reviewer_only": _co_failure(codex_miss_ro, agy_miss_ro, reviewer_only_def),
        "co_false_alarm_cleans": _co_failure(codex_fa, agy_fa, clean_ids),
    }


def _fmt_arm(a: dict) -> str:
    cdr, cci = a.get("caught_defect_rate"), a.get("caught_defect_ci95")
    far, fci = a.get("false_alarm_rate"), a.get("false_alarm_ci95")
    return (f"caught={cdr} CI{cci} ({a.get('caught')}/{a.get('defects')}) | "
            f"FAR={far} CI{fci} ({a.get('false_alarms')}/{a.get('cleans')})")


def _print_report(report: dict) -> None:
    for sname, s in report["slices"].items():
        print(f"\n==== OFFLINE LOCAL — slice {sname} (n={s['n']}, def={s['defects']}, clean={s['cleans']}, "
              f"reviewer-only-def={s['reviewer_only_defects']}) ====")
        print("  usable-rate:", s["usable_rate"])
        for name, a in s["arms"].items():
            print(f"  {name:26} {_fmt_arm(a)}")
        print("  -- decorrelation (co-failure) --")
        for pair, d in s["decorrelation"].items():
            cm = d["co_miss_all_defects"]; cf = d["co_false_alarm_cleans"]
            print(f"   {pair}: co-miss(def) both={cm['both_fail']}/{cm['n']} obs={cm['obs_joint']} "
                  f"indep={cm['indep_joint']} excess={cm['excess_over_indep']} phi={cm['phi']} | "
                  f"co-FA(clean) both={cf['both_fail']}/{cf['n']} phi={cf['phi']}")
    fc = report.get("frontier_comparison", {})
    if "co_miss_all_defects" in fc:
        cm = fc["co_miss_all_defects"]; cf = fc["co_false_alarm_cleans"]
        print(f"\n==== FRONTIER (codex|agy, held_out, {fc.get('source')}) ====")
        print(f"   co-miss(def) both={cm['both_fail']}/{cm['n']} obs={cm['obs_joint']} "
              f"indep={cm['indep_joint']} excess={cm['excess_over_indep']} phi={cm['phi']} | "
              f"co-FA(clean) both={cf['both_fail']}/{cf['n']} phi={cf['phi']}")


def _arg_list(flag, default):
    v = next((a.split("=", 1)[1] for a in sys.argv if a.startswith(flag + "=")), None)
    return default if v is None else [x.strip() for x in v.split(",") if x.strip()]


def _arg_int(flag):
    v = next((a.split("=", 1)[1] for a in sys.argv if a.startswith(flag + "=")), None)
    return int(v) if v is not None else None


def main() -> int:
    if "--score" in sys.argv:
        return score()
    if "--collect" in sys.argv:
        return collect()
    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
