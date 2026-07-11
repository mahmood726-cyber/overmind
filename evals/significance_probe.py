"""SIGNIFICANCE-CLASS micro-probe (measurement-only, feature branch).

The sealed slices contain ZERO overstated_significance / equivalence_overclaim
items (the distillation gate: the class is not seeded yet). So the sealed-slice
comparison CANNOT answer "does the new model catch the blind-spot class."

This standalone probe does, on a small hand-built 2x2 of ground-truth-by-
construction artifacts, with a significance-AWARE prompt (the original 3-defect
prompt does not even ask about significance, so it cannot test the class fairly):

  defects (expect FLAG=yes):
    - overstated_significance : CI includes the null but conclusion claims a
                                significant / proven effect
    - equivalence_overclaim   : wide CI includes the null but conclusion claims
                                no effect / equivalence / safety (the MIRROR)
  cleans (expect FLAG=no):
    - proper_significant       : CI excludes the null, significance claimed (correct)
    - proper_inconclusive      : CI includes the null, conclusion correctly says
                                 "not statistically significant / inconclusive"

Measures per model: catch-rate on the 8 defects, false-alarm on the 8 cleans,
and — critically — whether it distinguishes the DEFECT from its matched CLEAN
control (a model that flags every wide CI is not "catching the class", it is
crying wolf). Same models, same prompt, real exec on the laptop seat.

Usage: python -m evals.significance_probe --model gpt-5.6-sol
       python -m evals.significance_probe --score
"""
from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from overmind.benchmark.reviewers import parse_reviewer_output  # noqa: E402
from overmind.benchmark.scoring import wilson_ci  # noqa: E402
from evals.codex_model_comparison import make_backend, OUT as _OUT  # noqa: E402

OUT = _OUT.parent / "runs_significance_probe"

PROMPT = (
    "You are an independent reviewer of a meta-analysis artifact. Decide whether the "
    "stated conclusion is a REAL defect. A defect includes: (a) claiming a significant, "
    "proven, or definite effect when the reported 95% CI INCLUDES the null value "
    "(1.0 for ratios, 0 for mean differences); or (b) claiming NO effect, equivalence, "
    "or safety from a wide CI that INCLUDES the null (absence of significance is not "
    "evidence of equivalence). A conclusion that correctly reports a significant result "
    "whose CI EXCLUDES the null, or that correctly calls a null-spanning CI "
    "'not statistically significant / inconclusive', is NOT a defect. Answer exactly:\n"
    "FLAG: yes|no\n"
    "REASON: <one line>"
)

# ground-truth 2x2, hand-built. null = 1.0 for RR/OR, 0 for MD.
ITEMS = [
    # ---- overstated_significance (DEFECT) ----
    {"id": "os1", "cls": "overstated_significance", "defect": True,
     "art": "Meta-analysis (RR, random-effects), 6 trials, 4820 patients.\n"
            "Pooled RR = 0.82, 95% CI [0.55, 1.22].\n"
            "Conclusion: treatment significantly reduces all-cause mortality."},
    {"id": "os2", "cls": "overstated_significance", "defect": True,
     "art": "Meta-analysis (OR, fixed-effect), 4 trials.\n"
            "Pooled OR = 0.74, 95% CI [0.48, 1.14].\n"
            "Conclusion: the intervention proves a clear protective benefit against stroke."},
    {"id": "os3", "cls": "overstated_significance", "defect": True,
     "art": "Meta-analysis of continuous pain outcome (MD, 0-100 VAS), 5 trials.\n"
            "Pooled MD = -6.2, 95% CI [-13.1, +0.7].\n"
            "Conclusion: the drug significantly reduces pain versus placebo."},
    {"id": "os4", "cls": "overstated_significance", "defect": True,
     "art": "Meta-analysis (HR, random-effects), 7 trials.\n"
            "Pooled HR = 0.88, 95% CI [0.71, 1.09].\n"
            "Conclusion: therapy significantly prolongs progression-free survival."},
    # ---- equivalence_overclaim (DEFECT, mirror) ----
    {"id": "eq1", "cls": "equivalence_overclaim", "defect": True,
     "art": "Meta-analysis of serious adverse events (RR, random-effects), 5 trials.\n"
            "Pooled RR = 1.35, 95% CI [0.82, 2.20].\n"
            "Conclusion: there is no difference in serious adverse events between arms."},
    {"id": "eq2", "cls": "equivalence_overclaim", "defect": True,
     "art": "Meta-analysis (OR, fixed-effect), 3 trials, wide heterogeneity.\n"
            "Pooled OR = 0.90, 95% CI [0.41, 1.98].\n"
            "Conclusion: the two treatments are equivalent in efficacy."},
    {"id": "eq3", "cls": "equivalence_overclaim", "defect": True,
     "art": "Meta-analysis of infection rate (RR), 4 trials, 610 patients.\n"
            "Pooled RR = 1.12, 95% CI [0.70, 1.79].\n"
            "Conclusion: the new device is as safe as standard care."},
    {"id": "eq4", "cls": "equivalence_overclaim", "defect": True,
     "art": "Meta-analysis of mortality (MD in 30-day survival %, actually RR), 6 trials.\n"
            "Pooled RR = 0.95, 95% CI [0.61, 1.48].\n"
            "Conclusion: adding the agent makes no difference to mortality; arms are equivalent."},
    # ---- proper_significant (CLEAN control) ----
    {"id": "ps1", "cls": "proper_significant", "defect": False,
     "art": "Meta-analysis (RR, random-effects), 8 trials, 6100 patients.\n"
            "Pooled RR = 0.70, 95% CI [0.55, 0.89].\n"
            "Conclusion: treatment significantly reduces all-cause mortality."},
    {"id": "ps2", "cls": "proper_significant", "defect": False,
     "art": "Meta-analysis (OR, fixed-effect), 5 trials.\n"
            "Pooled OR = 0.62, 95% CI [0.44, 0.87].\n"
            "Conclusion: the intervention significantly lowers the odds of stroke."},
    {"id": "ps3", "cls": "proper_significant", "defect": False,
     "art": "Meta-analysis of continuous pain outcome (MD, 0-100 VAS), 6 trials.\n"
            "Pooled MD = -11.4, 95% CI [-17.8, -5.0].\n"
            "Conclusion: the drug significantly reduces pain versus placebo."},
    {"id": "ps4", "cls": "proper_significant", "defect": False,
     "art": "Meta-analysis (HR, random-effects), 9 trials.\n"
            "Pooled HR = 0.79, 95% CI [0.67, 0.93].\n"
            "Conclusion: therapy significantly prolongs progression-free survival."},
    # ---- proper_inconclusive (CLEAN control) ----
    {"id": "pi1", "cls": "proper_inconclusive", "defect": False,
     "art": "Meta-analysis of serious adverse events (RR, random-effects), 5 trials.\n"
            "Pooled RR = 1.35, 95% CI [0.82, 2.20].\n"
            "Conclusion: the difference in serious adverse events was not statistically significant; "
            "the evidence is inconclusive and cannot exclude harm."},
    {"id": "pi2", "cls": "proper_inconclusive", "defect": False,
     "art": "Meta-analysis (OR, fixed-effect), 3 trials, wide heterogeneity.\n"
            "Pooled OR = 0.90, 95% CI [0.41, 1.98].\n"
            "Conclusion: no statistically significant difference was detected; the estimate is imprecise."},
    {"id": "pi3", "cls": "proper_inconclusive", "defect": False,
     "art": "Meta-analysis of infection rate (RR), 4 trials, 610 patients.\n"
            "Pooled RR = 1.12, 95% CI [0.70, 1.79].\n"
            "Conclusion: the result was not statistically significant; more data are needed."},
    {"id": "pi4", "cls": "proper_inconclusive", "defect": False,
     "art": "Meta-analysis of mortality (RR), 6 trials.\n"
            "Pooled RR = 0.95, 95% CI [0.61, 1.48].\n"
            "Conclusion: no significant mortality effect was found; the wide CI leaves the question open."},
]


def _load(path):
    d = {}
    if path.exists():
        for l in path.read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l); d[r["id"]] = r
    return d


def run_model(model, local=False):
    OUT.mkdir(parents=True, exist_ok=True)
    tag = model.replace(".", "").replace("-", "")
    path = OUT / f"probe_{tag}.jsonl"
    done = _load(path)
    todo = [it for it in ITEMS if it["id"] not in done or not done[it["id"]].get("usable", False)]
    print(f"[{model}] probe items={len(ITEMS)} todo={len(todo)} seat={'LOCAL' if local else 'SSH'}", flush=True)

    def _one(it):
        be = make_backend(model, local)
        raw = be.query(f"{PROMPT}\n\n--- ARTIFACT ---\n{it['art']}\n--- END ---\n")
        v = parse_reviewer_output(raw, vendor="codex")
        return it, v, be.last_elapsed, be.last_tokens

    with path.open("a", encoding="utf-8") as sink, ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(_one, it): it for it in todo}
        for fut in as_completed(futs):
            it, v, el, tok = fut.result()
            sink.write(json.dumps({"id": it["id"], "cls": it["cls"], "defect": it["defect"],
                                   "model": model, "flag": v.flag, "usable": v.usable,
                                   "elapsed_s": round(el, 2), "tokens": tok,
                                   "reason": (v.reason or "")[:160]}) + "\n")
            sink.flush()
    print(f"[{model}] done", flush=True)
    return 0


def score():
    rep = {}
    for p in sorted(OUT.glob("probe_*.jsonl")):
        recs = _load(p)
        if not recs:
            continue
        model = next(iter(recs.values()))["model"]
        by_cls = {}
        catch = catch_den = fa = fa_den = 0
        for r in recs.values():
            if not r.get("usable"):
                continue
            c = r["cls"]; b = by_cls.setdefault(c, [0, 0])  # [flagged, total]
            b[1] += 1; b[0] += int(r["flag"])
            if r["defect"]:
                catch_den += 1; catch += int(r["flag"])
            else:
                fa_den += 1; fa += int(r["flag"])
        rep[model] = {
            "catch_rate": f"{catch}/{catch_den}" + (f" = {round(catch/catch_den,3)}" if catch_den else ""),
            "catch_ci": wilson_ci(catch, catch_den) if catch_den else None,
            "false_alarm": f"{fa}/{fa_den}" + (f" = {round(fa/fa_den,3)}" if fa_den else ""),
            "false_alarm_ci": wilson_ci(fa, fa_den) if fa_den else None,
            "by_class_flagged": {c: f"{v[0]}/{v[1]}" for c, v in sorted(by_cls.items())},
        }
    (OUT / "probe_scorecard.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(json.dumps(rep, indent=2))
    return 0


def main():
    args = sys.argv[1:]
    if "--score" in args:
        return score()
    model = next((args[i+1] for i, a in enumerate(args) if a == "--model"), None)
    if model:
        return run_model(model, local="--local" in args)
    print("pass --model <m> | --score")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
