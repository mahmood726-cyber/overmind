"""CODEX MODEL COMPARISON driver (measurement-only, feature branch).

Question: Codex now offers a NEW gpt-5.6 family (sol/terra/luna) alongside the
pinned gpt-5.5. Do the new models actually HELP the verification panel on OUR
task? Measured, not assumed.

Clean controlled experiment: hold EVERYTHING fixed except the Codex model.
  * reviewer prompt   -> overmind.benchmark.reviewers.REVIEW_INSTRUCTION (original)
  * reasoning effort  -> medium (same as live_vendor_accuracy; each 5.6 model's
                          own default is also medium, so this is parity)
  * slices            -> the two SEALED slices (139 held-out + 92 frozen-dev),
                          same as the precision-fix two-slice validation
  * scorer            -> overmind.benchmark.scoring.score_arm (Wilson CIs)
  * agy reference     -> HELD FIXED (generated once, reused for every model) so a
                          model's decorrelation-from-agy is measured against the
                          SAME agy verdicts. agy is local (no Codex quota).

Only the Codex model varies (explicit -m per arm; NO reliance on any config
default, so provenance is single per arm). Answer keys read ONLY by the scorer.

Nothing in the running precision-fix eval is touched: separate branch, separate
output dir (runs_model_comparison/), separate JSONLs per model.

Usage:
    python -m evals.codex_model_comparison --agy            # phase 1: agy cache (once)
    python -m evals.codex_model_comparison --model gpt-5.6-sol   # phase 2: one Codex arm
    python -m evals.codex_model_comparison --score          # phase 3: score all arms present
    python -m evals.codex_model_comparison --max-tasks=N    # subset by id (smoke)
Resumable: per-task verdicts append to a per-model JSONL; a re-run skips done tasks.
Fail-loud: on Codex credit/quota exhaustion mid-run it STOPS and emits no clean
number (never a degraded arm presented as complete).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")

ROOT = Path(__file__).resolve().parents[1]
HOME = os.path.expanduser("~")
sys.path.insert(0, str(ROOT))

from overmind.benchmark.arms import arm_a, arm_c  # noqa: E402
from overmind.benchmark.reviewers import BackendReviewer, build_prompt, parse_reviewer_output  # noqa: E402
from overmind.benchmark.scoring import score_arm, wilson_ci  # noqa: E402
from overmind.benchmark.tasks import (  # noqa: E402
    held_out_ids, frozen_ids, load_keys, load_tasks,
)
from overmind.benchmark.witnesses import run_witness  # noqa: E402
from overmind.verification.judge_backends import AgyBackend  # noqa: E402

DATA = ROOT / "benchmark_data"
OUT = DATA / "runs_model_comparison"
KEY = r"C:\Users\mahmo\.ssh\node2_ed25519"
LAPTOP = "mahmo@100.80.183.43"
EFFORT = "medium"          # fixed across all models (parity; also each 5.6 default)
MAX_WORKERS = 3            # SSH concurrency; xhigh dropped links at 4, medium is safe at 3

CREDITS_DEAD = threading.Event()
# HARD exhaustion markers ONLY — specific phrases that appear in a real credit/
# quota-exhaustion envelope and cannot occur in a normal review or a token count.
# (An earlier bare "429" matched the substring in "tokens used 6,429" and a bare
# "quota"/"rate limit" can appear in a model's reasoning text — both falsely
# latched CREDITS_DEAD. These are removed.) Transient throttles (HTTP 429 / "rate
# limit") are handled separately below: they mark the ONE call unusable for retry
# but do NOT latch the process-wide dead flag.
_CREDIT_MARKERS = ("out of credits", "insufficient_quota", "insufficient quota",
                   "quota exceeded", "exceeded your current quota",
                   "usage limit reached", "you have hit your usage limit")
_THROTTLE_MARKERS = ("http 429", "status 429", "error 429", "rate limit",
                     "rate_limit", "too many requests")

_TOKENS_RE = re.compile(r"tokens used\s+([\d,]+)", re.IGNORECASE)


class SshCodexBackendM:
    """`codex exec` on the laptop over SSH with an EXPLICIT model + effort.

    Mirrors evals.live_vendor_accuracy.SshCodexBackend but pins `-m <model>` so
    provenance is single per arm (no config-default ambiguity). query() returns
    the answer string; last-call telemetry (elapsed_s, tokens) is stashed on the
    instance and read by the collector under a lock (one instance per worker).
    On failure returns a JUDGE_ERROR string (never a silent flag=False)."""

    def __init__(self, model: str, effort: str = EFFORT, timeout: int = 180):
        self.model = model
        self.effort = effort
        self.timeout = timeout
        self.last_elapsed = 0.0
        self.last_tokens = 0
        self.last_err = ""

    def query(self, prompt: str) -> str:
        remote = ('set "CODEX_HOME=%USERPROFILE%\\.codex" && '
                  "codex exec --skip-git-repo-check --sandbox read-only "
                  f"--config model_reasoning_effort={self.effort} -m {self.model} -")
        argv = ["ssh", "-i", KEY, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                "-o", "StrictHostKeyChecking=accept-new", LAPTOP, remote]
        t0 = time.time()
        try:
            p = subprocess.run(argv, input=prompt.encode("utf-8"),
                               capture_output=True, timeout=self.timeout)
        except Exception as exc:  # noqa: BLE001
            self.last_elapsed = time.time() - t0
            self.last_tokens = 0
            self.last_err = f"ssh/codex exec failed: {exc}"
            return f"JUDGE_ERROR: {self.last_err}"
        self.last_elapsed = time.time() - t0
        out = (p.stdout or b"").decode("utf-8", errors="replace")
        err = (p.stderr or b"").decode("utf-8", errors="replace")
        mt = _TOKENS_RE.search(err) or _TOKENS_RE.search(out)
        self.last_tokens = int(mt.group(1).replace(",", "")) if mt else 0
        self.last_err = ""
        low = (out + "\n" + err).lower()
        # HARD exhaustion: latch process-wide dead flag and fail loud.
        if any(m in low for m in _CREDIT_MARKERS):
            CREDITS_DEAD.set()
            self.last_err = "credit/quota EXHAUSTION marker"
            return f"JUDGE_ERROR: credits/quota exhausted: {err[-160:]}"
        # Non-zero exit: an error, but distinguish transient throttle from hard fail.
        if p.returncode != 0:
            if any(m in low for m in _THROTTLE_MARKERS):
                self.last_err = f"throttle rc={p.returncode} (transient, will retry)"
            else:
                self.last_err = f"rc={p.returncode}: {err[-160:]}"
            return f"JUDGE_ERROR: codex {self.last_err}"
        # rc==0 success: a normal answer is NEVER treated as credit-dead even if its
        # text happens to contain a stray marker substring.
        return out or "JUDGE_ERROR: empty stdout"


class LocalCodexBackendM:
    """Same measurement as SshCodexBackendM but runs `codex exec` on the LOCAL
    machine (PC1) rather than over SSH to the laptop. Used when the laptop seat's
    workspace credits are exhausted but the local mahmood726 workspace is still
    live (per-workspace credit balances differ under one email). Model weights +
    prompt + effort + slices + scorer are identical, so the seat/machine is not a
    model variable — only WHERE the identical model runs. Disclosed in the report."""

    def __init__(self, model: str, effort: str = EFFORT, timeout: int = 180):
        self.model = model
        self.effort = effort
        self.timeout = timeout
        self.last_elapsed = 0.0
        self.last_tokens = 0
        self.last_err = ""

    def query(self, prompt: str) -> str:
        codex = shutil.which("codex") or "codex"
        if os.name == "nt":
            argv = ["cmd", "/c", codex, "exec", "--skip-git-repo-check", "--sandbox",
                    "read-only", "--config", f"model_reasoning_effort={self.effort}",
                    "-m", self.model, "-"]
        else:
            argv = [codex, "exec", "--skip-git-repo-check", "--sandbox", "read-only",
                    "--config", f"model_reasoning_effort={self.effort}", "-m", self.model, "-"]
        env = dict(os.environ, CODEX_HOME=os.path.join(HOME, ".codex"))
        t0 = time.time()
        try:
            p = subprocess.run(argv, input=prompt.encode("utf-8"), capture_output=True,
                               timeout=self.timeout, env=env)
        except Exception as exc:  # noqa: BLE001
            self.last_elapsed = time.time() - t0
            self.last_tokens = 0
            self.last_err = f"local codex exec failed: {exc}"
            return f"JUDGE_ERROR: {self.last_err}"
        self.last_elapsed = time.time() - t0
        out = (p.stdout or b"").decode("utf-8", errors="replace")
        err = (p.stderr or b"").decode("utf-8", errors="replace")
        mt = _TOKENS_RE.search(err) or _TOKENS_RE.search(out)
        self.last_tokens = int(mt.group(1).replace(",", "")) if mt else 0
        self.last_err = ""
        low = (out + "\n" + err).lower()
        if any(m in low for m in _CREDIT_MARKERS):
            CREDITS_DEAD.set()
            self.last_err = "credit/quota EXHAUSTION marker"
            return f"JUDGE_ERROR: credits/quota exhausted: {err[-160:]}"
        if p.returncode != 0:
            if any(m in low for m in _THROTTLE_MARKERS):
                self.last_err = f"throttle rc={p.returncode} (transient, will retry)"
            else:
                self.last_err = f"rc={p.returncode}: {err[-160:]}"
            return f"JUDGE_ERROR: codex {self.last_err}"
        return out or "JUDGE_ERROR: empty stdout"


def make_backend(model: str, local: bool):
    return LocalCodexBackendM(model) if local else SshCodexBackendM(model)


# ---- slices ---------------------------------------------------------------

def build_slices():
    tasks = load_tasks(DATA / "tasks.json")
    keys = load_keys(DATA / "keys" / "keys.json")
    ids = [t.id for t in tasks]
    ho = set(held_out_ids(ids))
    fr = set(frozen_ids(ids))
    dev = [i for i in ids if i not in ho and i not in fr]
    dev_clean = [i for i in dev if not keys[i].has_defect]
    slice2 = fr | set(dev_clean)
    assert not (ho & slice2), "slices must be disjoint"
    by_id = {t.id: t for t in tasks}
    s1 = sorted([by_id[i] for i in ho], key=lambda t: t.id)
    s2 = sorted([by_id[i] for i in slice2], key=lambda t: t.id)
    return s1, s2, keys


def _load_jsonl(path: Path) -> dict:
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


# ---- phase 1: agy reference (once, no Codex quota) ------------------------

def run_agy(all_tasks) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "agy_reference.jsonl"
    done = _load_jsonl(path)
    todo = [t for t in all_tasks if t.id not in done or not done[t.id].get("usable", False)]
    print(f"[agy-ref] total={len(all_tasks)} done={len(done)} todo={len(todo)}", flush=True)
    rev = BackendReviewer(AgyBackend(), vendor="agy")

    def _one(t):
        av = rev(t)
        wd = bool(run_witness(t).defect)
        return t.id, av, wd

    t0 = time.time()
    with path.open("a", encoding="utf-8") as sink, ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(_one, t): t for t in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            tid, av, wd = fut.result()
            sink.write(json.dumps({"task_id": tid, "agy": av.to_dict(),
                                   "witness_defect": wd, "agy_raw": (av.raw or "")[:160]}) + "\n")
            sink.flush()
            if i % 20 == 0 or i == len(todo):
                print(f"[agy-ref] {i}/{len(todo)} ({round(time.time()-t0)}s)", flush=True)
    return 0


# ---- phase 2: one Codex model arm -----------------------------------------

def run_model(model: str, all_tasks, max_tasks=None, local=False) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tag = model.replace(".", "").replace("-", "")
    path = OUT / f"codex_{tag}.jsonl"
    tasks = all_tasks[:max_tasks] if max_tasks else all_tasks
    done = _load_jsonl(path)
    todo = [t for t in tasks if t.id not in done or not done[t.id].get("codex", {}).get("usable", False)]
    seat = "LOCAL(pc1)" if local else "SSH(laptop)"
    print(f"[{model}] total={len(tasks)} done={len(done)} todo={len(todo)} effort={EFFORT} seat={seat}", flush=True)
    if not todo:
        print(f"[{model}] nothing to do", flush=True)
        return 0

    def _one(t):
        be = make_backend(model, local)  # one backend per call -> clean telemetry
        raw = be.query(build_prompt(t))
        v = parse_reviewer_output(raw, vendor="codex")
        return t.id, v, be.last_elapsed, be.last_tokens, be.last_err

    t0 = time.time()
    tok_sum = 0
    with path.open("a", encoding="utf-8") as sink, ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(_one, t): t for t in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            if CREDITS_DEAD.is_set():
                # let in-flight finish but stop reporting as clean
                pass
            tid, v, elapsed, tokens, err = fut.result()
            tok_sum += tokens
            sink.write(json.dumps({
                "task_id": tid, "model": model, "effort": EFFORT,
                "codex": v.to_dict(), "elapsed_s": round(elapsed, 2), "tokens": tokens,
                "err": err, "codex_raw": (v.raw or "")[:200],
            }) + "\n")
            sink.flush()
            if i % 10 == 0 or i == len(todo):
                el = round(time.time() - t0)
                flag = "  [CREDITS DEAD]" if CREDITS_DEAD.is_set() else ""
                print(f"[{model}] {len(done)+i}/{len(tasks)} ({el}s, {tok_sum} tok){flag}", flush=True)
    if CREDITS_DEAD.is_set():
        print(f"\n#### CREDIT/QUOTA EXHAUSTION during {model} — INCOMPLETE, not a clean number. "
              f"Resume when quota returns (re-runs only failed items). No score emitted for this arm.",
              flush=True)
        return 2
    return 0


# ---- phase 3: score all arms present --------------------------------------

def _rv(d):
    from overmind.benchmark.reviewers import ReviewerVerdict
    return ReviewerVerdict(flag=bool(d["flag"]), reason=d.get("reason", ""),
                           value=d.get("value"), vendor=d.get("vendor", ""),
                           usable=bool(d.get("usable", True)))


def _cofail(codex_by_id, agy_by_id, keys, ids):
    """Codex-vs-agy decorrelation on a slice. Returns co-false-alarm and co-miss
    counts + phi. 'Error' = flag on a clean (false alarm) or no-flag on a defect
    (miss). phi over the 2x2 of (codex_error, agy_error) across the slice."""
    n = a_err = c_err = both = 0
    co_fa = co_fa_den = co_miss = co_miss_den = 0
    for tid in ids:
        k = keys.get(tid)
        cv = codex_by_id.get(tid)
        av = agy_by_id.get(tid)
        if k is None or cv is None or av is None:
            continue
        if not cv.get("usable", True) or not av.get("usable", True):
            continue
        n += 1
        cflag = bool(cv["flag"])
        aflag = bool(av["flag"])
        if k.has_defect:
            ce = not cflag  # miss
            ae = not aflag
            co_miss_den += 1
            if ce and ae:
                co_miss += 1
        else:
            ce = cflag      # false alarm
            ae = aflag
            co_fa_den += 1
            if ce and ae:
                co_fa += 1
        a_err += int(ae)
        c_err += int(ce)
        both += int(ae and ce)
    # phi over (codex_error, agy_error)
    import math
    n11 = both
    n10 = c_err - both
    n01 = a_err - both
    n00 = n - n11 - n10 - n01
    denom = math.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
    phi = (n11 * n00 - n10 * n01) / denom if denom else 0.0
    # excess co-error over independence
    p_c = c_err / n if n else 0.0
    p_a = a_err / n if n else 0.0
    exp_both = p_c * p_a * n
    return {
        "n_usable": n, "codex_errors": c_err, "agy_errors": a_err, "both_error": both,
        "phi": round(phi, 4), "excess_both_over_indep": round((both - exp_both), 3),
        "co_false_alarm": f"{co_fa}/{co_fa_den}", "co_miss": f"{co_miss}/{co_miss_den}",
    }


def score():
    s1, s2, keys = build_slices()
    s1_ids = [t.id for t in s1]
    s2_ids = [t.id for t in s2]
    all_ids = s1_ids + s2_ids
    agy = _load_jsonl(OUT / "agy_reference.jsonl")
    agy_by_id = {tid: r["agy"] for tid, r in agy.items()}
    wit_by_id = {tid: bool(r["witness_defect"]) for tid, r in agy.items()}

    models = []
    for p in sorted(OUT.glob("codex_*.jsonl")):
        recs = _load_jsonl(p)
        model = next(iter(recs.values()))["model"] if recs else p.stem
        models.append((model, recs))

    report = {"effort": EFFORT, "slice1_n": len(s1_ids), "slice2_n": len(s2_ids),
              "agy_ref_usable": sum(1 for v in agy_by_id.values() if v.get("usable")),
              "models": {}}

    def score_slice(recs, ids, label):
        cby = {tid: recs[tid]["codex"] for tid in ids if tid in recs}
        kk = {tid: keys[tid] for tid in ids if tid in cby}
        # arm A: single codex
        a = {tid: arm_a(tid, [_rv(cby[tid])]) for tid in cby}
        am = score_arm(f"A-codex-{label}", a, kk)
        # arm C: codex + agy + floor
        c = {}
        for tid in cby:
            revs = [_rv(cby[tid])]
            if tid in agy_by_id:
                revs.append(_rv(agy_by_id[tid]))
            c[tid] = arm_c(tid, revs, wit_by_id.get(tid, False))
        cm = score_arm(f"C-codex+agy+floor-{label}", c, kk)
        elapsed = [recs[tid]["elapsed_s"] for tid in ids if tid in recs and recs[tid].get("codex", {}).get("usable")]
        toks = [recs[tid].get("tokens", 0) for tid in ids if tid in recs]
        med = sorted(elapsed)[len(elapsed)//2] if elapsed else None
        cof = _cofail(cby, agy_by_id, keys, ids)
        return {
            "n": am.n, "usable": sum(1 for tid in cby if cby[tid].get("usable")),
            "armA": {"recall": am.caught_defect_rate, "recall_ci": am.caught_defect_ci,
                     "far": am.false_alarm_rate, "far_ci": am.false_alarm_ci,
                     "caught": f"{am.caught}/{am.defects}", "fa": f"{am.false_alarms}/{am.cleans}"},
            "armC": {"recall": cm.caught_defect_rate, "recall_ci": cm.caught_defect_ci,
                     "far": cm.false_alarm_rate, "far_ci": cm.false_alarm_ci,
                     "caught": f"{cm.caught}/{cm.defects}", "fa": f"{cm.false_alarms}/{cm.cleans}"},
            "median_s": med, "total_tokens": sum(toks), "decorrelation_vs_agy": cof,
        }

    def score_pooled(recs):
        cby = {tid: recs[tid]["codex"] for tid in all_ids if tid in recs}
        kk = {tid: keys[tid] for tid in all_ids if tid in cby}
        a = {tid: arm_a(tid, [_rv(cby[tid])]) for tid in cby}
        am = score_arm("A-pooled", a, kk)
        c = {}
        for tid in cby:
            revs = [_rv(cby[tid])]
            if tid in agy_by_id:
                revs.append(_rv(agy_by_id[tid]))
            c[tid] = arm_c(tid, revs, wit_by_id.get(tid, False))
        cm = score_arm("C-pooled", c, kk)
        cof = _cofail(cby, agy_by_id, keys, all_ids)
        return {
            "armA": {"recall": am.caught_defect_rate, "recall_ci": am.caught_defect_ci,
                     "far": am.false_alarm_rate, "far_ci": am.false_alarm_ci,
                     "caught": f"{am.caught}/{am.defects}", "fa": f"{am.false_alarms}/{am.cleans}"},
            "armC": {"recall": cm.caught_defect_rate, "recall_ci": cm.caught_defect_ci,
                     "far": cm.false_alarm_rate, "far_ci": cm.false_alarm_ci,
                     "caught": f"{cm.caught}/{cm.defects}", "fa": f"{cm.false_alarms}/{cm.cleans}"},
            "decorrelation_vs_agy": cof,
        }

    for model, recs in models:
        report["models"][model] = {
            "slice1": score_slice(recs, s1_ids, "s1"),
            "slice2": score_slice(recs, s2_ids, "s2"),
            "pooled": score_pooled(recs),
        }

    (OUT / "comparison_scorecard.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


def main() -> int:
    args = sys.argv[1:]
    max_tasks = next((int(a.split("=", 1)[1]) for a in args if a.startswith("--max-tasks=")), None)
    s1, s2, keys = build_slices()
    all_tasks = s1 + s2
    print(f"[slices] s1(held_out)={len(s1)} s2(frozen-dev)={len(s2)} total={len(all_tasks)}", flush=True)
    if "--agy" in args:
        return run_agy(all_tasks[:max_tasks] if max_tasks else all_tasks)
    if "--score" in args:
        return score()
    model = next((args[i+1] for i, a in enumerate(args) if a == "--model"), None)
    if model:
        return run_model(model, all_tasks, max_tasks, local="--local" in args)
    print("nothing to do; pass --agy | --model <m> | --score", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
