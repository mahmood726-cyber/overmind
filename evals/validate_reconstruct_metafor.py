"""Cross-verify every load-bearing pooled number in the reconstruct-and-beat
harness against metafor (R 4.6.0, metafor 5.0.1) — the reference implementation.

metafor reference values are frozen here (regenerable via the R block in the
docstring). We assert overmind's DL/REML point+se+tau2 and the HKSJ CI match to a
tight tolerance. This is the third independent engine behind the pooled numbers
(overmind pooling.py; metafor; and R's escalc for the effect sizes). Codex and agy
were both out of quota this session (reported honestly in the writeup), so metafor
carries the external-verification load here — which for pure pooling arithmetic is
the stronger check than an LLM would be.

Regenerate the reference:
    Rscript -e 'library(metafor); d<-read.csv("F:/public-data/metadat/dat.bcg.csv");
                dat<-escalc("RR",ai=tpos,bi=tneg,ci=cpos,di=cneg,data=d);
                r<-rma(yi,vi,data=dat,method="REML"); print(c(r$beta,r$se,r$tau2))'
"""
from __future__ import annotations

import math

from evals.reconstruct_and_beat import TIER1, _load
from overmind.evidence.pooling import pool
from overmind.evidence.pooling_intervals import pool_with_intervals

# metafor 5.0.1 reference: key -> {DL:(est,se,tau2), REML:(est,se,tau2), HKSJ_ci:(lo,hi)}
METAFOR_REF = {
    "bcg_tb":                      {"DL": (-0.714117, 0.178742, 0.308760),
                                    "REML": (-0.714532, 0.179782, 0.313243),
                                    "HKSJ_ci": (-1.107821, -0.320413)},
    "magnesium_mi":                {"DL": (-0.412481, 0.111765, 0.066732),
                                    "REML": (-0.545850, 0.150353, 0.176562),
                                    "HKSJ_ci": (-0.661726, -0.163235)},
    "stroke_unit_los":             {"DL": (-13.981722, 5.126698, 205.409375),
                                    "REML": (-15.106027, 8.946553, 684.646153),
                                    "HKSJ_ci": (-34.128834, 6.165390)},
    "teacher_expectancy":          {"DL": (0.089322, 0.055794, 0.025904),
                                    "REML": (0.083708, 0.051646, 0.018826),
                                    "HKSJ_ci": (-0.044245, 0.222889)},
    "adherence_conscientiousness": {"DL": (0.149598, 0.031161, 0.007763),
                                    "REML": (0.149918, 0.031561, 0.008111),
                                    "HKSJ_ci": (0.079932, 0.219265)},
}

# Tolerances: DL is closed-form -> machine precision; REML/PM iterate -> looser;
# tau2 for the huge-variance stroke set (tau2~200-680) needs a relative check.
ATOL = 1e-4
RTOL_TAU2 = 2e-3


def _close(a, b, atol=ATOL, rtol=0.0):
    return abs(a - b) <= atol + rtol * abs(b)


def main() -> int:
    fails = []
    print(f"{'target':27s} {'cell':10s} {'overmind':>14s} {'metafor':>14s}  ok")
    for t in TIER1:
        ref = METAFOR_REF.get(t.key)
        if ref is None:
            continue
        studies, pmeasure, _ = _load(t)
        checks = []
        for method in ("DL", "REML"):
            r = pool(studies, pmeasure, method)
            m_est, m_se, m_tau2 = ref[method]
            checks.append((f"{method} est", r["estimate_log"], m_est, ATOL, 0.0))
            checks.append((f"{method} se", r["se"], m_se, ATOL, 0.0))
            tau2_atol = ATOL if abs(m_tau2) < 1 else 0.0
            checks.append((f"{method} tau2", r["tau2"], m_tau2, tau2_atol, RTOL_TAU2))
        iv = pool_with_intervals(studies, pmeasure, "DL")
        lo, hi = iv["hksj_ci_log"]
        checks.append(("HKSJ lo", lo, ref["HKSJ_ci"][0], ATOL, 0.0))
        checks.append(("HKSJ hi", hi, ref["HKSJ_ci"][1], ATOL, 0.0))
        for name, ov, mf, atol, rtol in checks:
            ok = _close(ov, mf, atol, rtol)
            if not ok:
                fails.append((t.key, name, ov, mf))
            print(f"{t.key:27s} {name:10s} {ov:>14.6f} {mf:>14.6f}  {'OK' if ok else 'FAIL'}")
    print()
    if fails:
        print(f"FAILED {len(fails)} cells:")
        for f in fails:
            print("  ", f)
        return 1
    print("ALL load-bearing pooled numbers match metafor within tolerance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
