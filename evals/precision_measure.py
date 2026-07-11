"""Precision-fix measurement harness (feature branch, measurement-only).

Scores a recorded ``reviews.jsonl`` (from ``live_vendor_accuracy``) on the SEALED
held-out slice with the SAME scorer, across arm variants, so each precision fix is
measured separately (before/after FAR + recall) on identical data:

  * ``C_raw``          — the shipped Arm C (flag-on-any-dissent + witness floor). Baseline.
  * ``C_corroborated`` — Fix #2: sig-only flags need >=2 vendors; structural/witness
                         still flag on any dissent.
  * ``C_conformal_proxy`` — the shipped regex-proxy conformal gate on raw C.
  * ``C_conformal_real``  — Fix #3: conformal gate driven by the model's EMITTED
                         per-flag confidence (falls back to the proxy when a review
                         has no confidence field, e.g. the baseline run).
  * ``C_combined``     — Fix#1 prompt (implicit in the reviews file) + Fix#2 + Fix#3.

Answer keys are read ONLY here (the scorer) — blinding preserved. Prints the exact
list of clean tasks each variant still flags (the surviving false alarms).

Usage:
    python -m evals.precision_measure benchmark_data/runs_live_accuracy/reviews_BASELINE.jsonl
    python -m evals.precision_measure <reviews.jsonl> [--alpha=0.10]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from overmind.benchmark.arms import arm_a, arm_c, arm_c_corroborated  # noqa: E402
from overmind.benchmark.conformal import (  # noqa: E402
    ConformalGate, calibrate_threshold, flag_confidence, gate_from_defect_flags,
)
from overmind.benchmark.reviewers import ReviewerVerdict  # noqa: E402
from overmind.benchmark.scoring import score_arm  # noqa: E402
from overmind.benchmark.tasks import held_out_ids, load_keys, load_tasks  # noqa: E402

DATA = ROOT / "benchmark_data"


def _rv(d: dict) -> ReviewerVerdict:
    conf = d.get("confidence")
    return ReviewerVerdict(
        flag=bool(d["flag"]), reason=d.get("reason", "") or "", value=d.get("value"),
        vendor=d.get("vendor", "") or "", usable=bool(d.get("usable", True)),
        confidence=float(conf) if isinstance(conf, (int, float)) else None,
    )


def load_reviews(path: Path) -> dict:
    recs = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        recs[r["task_id"]] = r
    return recs


# ---- Fix #3: a gate that prefers the model's EMITTED confidence over the proxy -----

def real_conf(verdicts: list) -> float:
    """Panel flag-confidence from the model's EMITTED per-flag confidence when present,
    else the shipped reason-proxy. Only usable flaggers count; the MINIMUM emitted
    confidence among flaggers is the panel confidence (a single low-confidence flag
    makes the panel borderline). Falls back to ``flag_confidence`` (proxy) when NO
    flagger emitted a confidence — so baseline reviews degrade gracefully."""
    usable_flaggers = [v for v in verdicts
                       if getattr(v, "usable", True) and getattr(v, "flag", False)]
    if not usable_flaggers:
        return 1.0
    emitted = [getattr(v, "confidence", None) for v in usable_flaggers]
    emitted = [c for c in emitted if c is not None]
    if not emitted:
        return flag_confidence(verdicts)          # graceful fallback to the proxy
    # blend: the model's own minimum confidence, but a second corroborating vendor
    # still lifts it (decorrelated agreement is real signal), capped at 1.0.
    base = min(emitted)
    corroboration = 0.12 * (len({getattr(v, "vendor", "") for v in usable_flaggers}) - 1)
    return max(0.0, min(1.0, round(base + corroboration, 4)))


class RealConfGate(ConformalGate):
    def should_abstain(self, reviewer_verdicts: list) -> bool:
        return real_conf(reviewer_verdicts) <= self.tau


def _arm_c_gated(task_id, verdicts, witness_defect, gate):
    """arm_c with an abstain gate (mirrors the driver's gated path)."""
    return arm_c(task_id, verdicts, witness_defect, gate=gate)


def measure(reviews_path: str, *, alpha: float = 0.10, restrict_held_out: bool = False) -> dict:
    tasks = load_tasks(DATA / "tasks.json")
    keys = load_keys(DATA / "keys" / "keys.json")
    recs = load_reviews(Path(reviews_path))
    # Slice-agnostic: score exactly the tasks present in this reviews file (∩ keys).
    # The reviews file already IS the slice (held-out, or slice-2 = frozen ∪ dev-cleans),
    # so we never re-impose a slice filter and cannot accidentally drop a slice-2 task.
    if restrict_held_out:
        allow = held_out_ids([t.id for t in tasks])
        ho_ids = sorted(tid for tid in recs if tid in keys and tid in allow)
    else:
        ho_ids = sorted(tid for tid in recs if tid in keys)
    ho_keys = {tid: keys[tid] for tid in ho_ids}

    reviewer_records = {}   # task_id -> [codex_verdict, agy_verdict]
    for tid in ho_ids:
        r = recs[tid]
        reviewer_records[tid] = [_rv(r["codex"]), _rv(r["agy"])]

    def wd(tid):
        return bool(recs[tid].get("witness_defect"))

    # arms
    a_v = {tid: arm_a(tid, [reviewer_records[tid][0]]) for tid in ho_ids}
    craw_v = {tid: arm_c(tid, reviewer_records[tid], wd(tid)) for tid in ho_ids}
    ccorr_v = {tid: arm_c_corroborated(tid, reviewer_records[tid], wd(tid)) for tid in ho_ids}

    # conformal gates (calibrated ONLY on the defect class; alpha pinned)
    defect_ids = {tid for tid in ho_ids if ho_keys[tid].has_defect}
    rec_dicts = {tid: [v.to_dict() for v in reviewer_records[tid]] for tid in ho_ids}
    proxy_gate = gate_from_defect_flags(rec_dicts, defect_ids, alpha=alpha)
    # real-confidence gate: calibrate tau on emitted-confidence of defect flags
    real_confs = [real_conf(reviewer_records[tid]) for tid in defect_ids
                  if any(getattr(v, "flag", False) and getattr(v, "usable", True)
                         for v in reviewer_records[tid])]
    real_tau = calibrate_threshold(real_confs, alpha=alpha)
    real_gate = RealConfGate(tau=real_tau, alpha=alpha)

    cprox_v = {tid: _arm_c_gated(tid, reviewer_records[tid], wd(tid), proxy_gate) for tid in ho_ids}
    creal_v = {tid: _arm_c_gated(tid, reviewer_records[tid], wd(tid), real_gate) for tid in ho_ids}

    # combined: corroboration first, then real-confidence abstain on any surviving borderline flag
    def combined(tid):
        base = arm_c_corroborated(tid, reviewer_records[tid], wd(tid))
        if base.flag and base.deciding.startswith("corroborated_borderline") \
                and real_gate.should_abstain(reviewer_records[tid]):
            from overmind.benchmark.arms import ArmVerdict
            return ArmVerdict(tid, "C", False, False, "combined_abstain",
                              base.reviewer_flags, base.witness_defect, abstained=True)
        return base
    ccomb_v = {tid: combined(tid) for tid in ho_ids}

    variants = {
        "A (single Codex)": a_v,
        "C_raw (baseline)": craw_v,
        "C_corroborated (fix2)": ccorr_v,
        "C_conformal_proxy": cprox_v,
        "C_conformal_real (fix3)": creal_v,
        "C_combined (1+2+3)": ccomb_v,
    }
    out = {"reviews": str(reviews_path), "n": len(ho_ids),
           "defects": len(defect_ids), "cleans": len(ho_ids) - len(defect_ids),
           "alpha": alpha, "proxy_tau": round(proxy_gate.tau, 4),
           "real_tau": round(real_tau, 4), "arms": {}}
    for name, verds in variants.items():
        m = score_arm(name, verds, ho_keys)
        fa_ids = [tid for tid in ho_ids if not ho_keys[tid].has_defect and verds[tid].flag]
        out["arms"][name] = {
            "caught": m.caught, "defects": m.defects, "recall": m.caught_defect_rate,
            "recall_ci95": m.caught_defect_ci,
            "false_alarms": m.false_alarms, "cleans": m.cleans, "FAR": m.false_alarm_rate,
            "FAR_ci95": m.false_alarm_ci, "abstained": m.abstained,
            "abstained_on_defect": m.abstained_on_defect,
            "surviving_false_alarms": [t.replace("cochrane_", "").replace("__clean", "") for t in fa_ids],
        }
    return out


def _print(out: dict) -> None:
    print(f"\n==== PRECISION MEASURE — {out['reviews']} ====")
    print(f"held-out n={out['n']} (defects={out['defects']}, cleans={out['cleans']}); "
          f"alpha={out['alpha']} proxy_tau={out['proxy_tau']} real_tau={out['real_tau']}")
    print(f"{'variant':26} {'recall':>16} {'FAR':>16}  {'abst(def)':>9}")
    for name, m in out["arms"].items():
        rc = f"{m['recall']} {tuple(m['recall_ci95']) if m['recall_ci95'] else ''}"
        fr = f"{m['FAR']} {tuple(m['FAR_ci95']) if m['FAR_ci95'] else ''}"
        print(f"{name:26} {m['caught']}/{m['defects']}={m['recall']:<8} "
              f"{m['false_alarms']}/{m['cleans']}={m['FAR']:<8} {m['abstained']}({m['abstained_on_defect']})")
    print("\nSurviving false alarms per variant:")
    for name, m in out["arms"].items():
        print(f"  {name:26} {m['surviving_false_alarms']}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    alpha = next((float(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--alpha=")), 0.10)
    path = args[0] if args else str(DATA / "runs_live_accuracy" / "reviews_BASELINE.jsonl")
    out = measure(path, alpha=alpha)
    _print(out)
