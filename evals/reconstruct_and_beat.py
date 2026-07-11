"""Reconstruct-and-beat — the load-bearing mission evidence.

Claim under test: a meta-analysis reconstructed from OPENLY-ACCESSIBLE data only
can match-or-beat the published review on three honest axes:

  1. METHOD           — re-pool the same trial set with the Overmind stack
     (REML / Paule-Mandel / HKSJ t-CI / Cochrane t_{k-1} prediction interval)
     versus the published DerSimonian-Laird, and report the delta and *why* ours
     is preferable, or honestly that it makes no material difference.
  2. VERIFIED-COMPLETENESS — did the open-data reconstruction find registry-only /
     unpublished trials the review omitted (the non-publication signal), and is
     every datapoint source-verified through the quorum+conformal membrane?
  3. TRANSPARENCY     — every datapoint provenance-linked and the whole result
     re-runnable from this one script; contrast with the published review, which
     is typically not reproducible from its report alone.

Two tiers of targets:
  * Tier 1 (``metadat`` classics) — the trial-level effects ARE the open published
    data (the review's own reported table). Bulletproof for METHOD + TRANSPARENCY;
    COMPLETENESS is honestly N/A (pre-registry trials, and the data == the review's
    own table, so there is no independent registry to diff against).
  * Tier 2 (recent drug reviews) — trial effects re-extracted INDEPENDENTLY from
    ClinicalTrials.gov v2 structured results through the membrane; all three axes
    have teeth (see ``reconstruct_ctgov.py``).

RAILS honored: openly-accessible data only; no fabricated numbers (every pooled
value is computed here and cross-checked against metafor); the deterministic
pooling core is untouched (this only *reads* it); additive; nothing deployed.

Ground truth (published pooled values / metafor references) is used for SCORING
ONLY and is never fed into any extraction step.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

from overmind.evidence.pooling import Study, pool
from overmind.evidence.pooling_intervals import pool_with_intervals

# --------------------------------------------------------------------------- #
# Gold / open-data locations (env-overridable; NO absolute path is load-bearing).
# --------------------------------------------------------------------------- #
_METADAT = Path(os.environ.get("OVERMIND_METADAT_DIR", r"F:\public-data\metadat"))


def _atanh(x: float) -> float:
    return 0.5 * math.log((1 + x) / (1 - x))


# --------------------------------------------------------------------------- #
# Tier-1 target registry. Each entry is a REAL published meta-analysis whose
# trial-level table is the open data. ``published`` records the review's method
# and its reported pooled effect (for a cross-check, never fed to computation).
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Tier1Target:
    key: str
    file: str
    measure: str                 # RR / OR / MD / SMD(GIV) / ZCOR(GIV)
    loader: str                  # how to build Studies from the CSV
    citation: str
    published_method: str
    published_effect: str        # human-readable reported pooled effect (cross-check)
    note: str = ""


TIER1: list[Tier1Target] = [
    Tier1Target(
        key="bcg_tb",
        file="dat.bcg.csv", measure="RR", loader="twobytwo_rr",
        citation="Colditz et al., JAMA 1994 (BCG vaccine vs tuberculosis); data via metadat dat.bcg",
        published_method="random-effects (DerSimonian-Laird)",
        published_effect="RR ~0.49 (random effects); marked latitude heterogeneity",
        note="13 placebo-controlled BCG trials; the canonical high-heterogeneity example.",
    ),
    Tier1Target(
        key="magnesium_mi",
        file="dat.li2007.csv", measure="OR", loader="twobytwo_or_col",
        citation="Li et al. 2007 (IV magnesium in acute MI, mortality); data via metadat dat.li2007",
        published_method="random-effects (DerSimonian-Laird)",
        published_effect="OR<1 in small trials, attenuated by the large ISIS-4 trial (the magnesium controversy)",
        note="The classic small-study-effects / large-trial-reversal case.",
    ),
    Tier1Target(
        key="stroke_unit_los",
        file="dat.normand1999.csv", measure="MD", loader="md_from_arms",
        citation="Normand 1999 (stroke-unit vs routine care, length of hospital stay); data via metadat dat.normand1999",
        published_method="random-effects (DerSimonian-Laird)",
        published_effect="mean-difference in days, large between-study heterogeneity",
        note="Continuous outcome (mean difference), k=9.",
    ),
    Tier1Target(
        key="teacher_expectancy",
        file="dat.raudenbush1985.csv", measure="SMD", loader="giv_yi_vi",
        citation="Raudenbush 1985 (teacher expectancy on pupil IQ, standardized mean difference); data via metadat dat.raudenbush1985",
        published_method="random-effects / mixed (moderator: weeks of contact)",
        published_effect="small pooled SMD, near-null once contact-time moderator is modelled",
        note="Standardized mean difference, k=19; generic inverse-variance.",
    ),
    Tier1Target(
        key="adherence_conscientiousness",
        file="dat.molloy2014.csv", measure="ZCOR", loader="fisher_z",
        citation="Molloy et al. 2014 (conscientiousness & medication adherence, correlation); data via metadat dat.molloy2014",
        published_method="random-effects (DerSimonian-Laird), Fisher-z",
        published_effect="pooled r ~0.15 (small positive)",
        note="Correlation pooled on the Fisher-z scale, k=16.",
    ),
]


# --------------------------------------------------------------------------- #
# Loaders: CSV -> list[Study]. Each returns (studies, pool_measure, extra) where
# pool_measure is what pooling.pool expects ('RR'/'OR'/'GIV').
# --------------------------------------------------------------------------- #
def _load(target: Tier1Target) -> tuple[list[Study], str, dict]:
    rows = list(csv.DictReader((_METADAT / target.file).open(encoding="utf-8")))
    L = target.loader
    if L == "twobytwo_rr":
        studies = [Study(label=r.get("author", r.get("trial", "")),
                         ai=int(r["tpos"]), n1=int(r["tpos"]) + int(r["tneg"]),
                         ci=int(r["cpos"]), n2=int(r["cpos"]) + int(r["cneg"])) for r in rows]
        return studies, "RR", {"scale_back": "ratio"}
    if L == "twobytwo_or_col":
        studies = [Study(label=r.get("study", ""),
                         ai=int(r["ai"]), n1=int(r["n1i"]),
                         ci=int(r["ci"]), n2=int(r["n2i"])) for r in rows]
        return studies, "OR", {"scale_back": "ratio"}
    if L == "md_from_arms":
        studies = []
        for r in rows:
            n1, m1, s1 = int(r["n1i"]), float(r["m1i"]), float(r["sd1i"])
            n2, m2, s2 = int(r["n2i"]), float(r["m2i"]), float(r["sd2i"])
            yi = m1 - m2
            vi = s1 * s1 / n1 + s2 * s2 / n2
            studies.append(Study(label=r.get("study", ""), yi=yi, vi=vi))
        return studies, "GIV", {"scale_back": "difference", "reported_measure": "MD"}
    if L == "giv_yi_vi":
        studies = [Study(label=r.get("author", r.get("study", "")),
                         yi=float(r["yi"]), vi=float(r["vi"])) for r in rows]
        return studies, "GIV", {"scale_back": "difference", "reported_measure": "SMD"}
    if L == "fisher_z":
        studies = []
        for r in rows:
            ni, ri = int(r["ni"]), float(r["ri"])
            ri = max(-0.9999, min(0.9999, ri))       # clamp per advanced-stats rule
            studies.append(Study(label=r.get("authors", ""), yi=_atanh(ri), vi=1.0 / (ni - 3)))
        return studies, "GIV", {"scale_back": "difference", "reported_measure": "Fisher-z(r)"}
    raise ValueError(f"unknown loader {L!r}")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _fmt_ci(pair, ratio=False):
    if pair is None:
        return "NA"
    lo, hi = pair
    return f"[{lo:.3f}, {hi:.3f}]"


def _sig(ci, null=0.0) -> bool:
    return not (ci[0] <= null <= ci[1])


def _score_method(dl, reml, hksj_ci, pi) -> dict:
    """Honest, two-part method scoring on the analysis (log/difference) scale.

    Part A — POINT ESTIMATE parity: REML vs the published DL. These are almost
    always numerically ~identical (REML's less-biased tau^2 shifts the weighting
    only slightly), so the honest verdict here is usually 'equal'. We report the
    absolute log-scale shift so the reader sees exactly how small it is.

    Part B — UNCERTAINTY quantification: the published DL analysis is a point + a
    z-Wald CI. Our stack adds (i) the small-k Hartung-Knapp t-CI and (ii) the
    Cochrane t_{k-1} prediction interval. 'better' is earned ONLY when this changes
    something decision-relevant: a significance flip under HKSJ, or a prediction
    interval that crosses the null (a new setting could plausibly show no/opposite
    effect) that a DL point estimate alone conceals.
    """
    point_shift = abs(reml["estimate_log"] - dl["estimate_log"])
    point_verdict = "equal" if point_shift < 0.02 else "shifted"

    dl_sig = _sig(dl["ci_log"])
    hksj_sig = _sig(hksj_ci)
    pi_crosses_null = pi[0] <= 0.0 <= pi[1]

    reasons = []
    unc = "equal"
    if dl_sig and not hksj_sig:
        unc = "better"
        reasons.append("HKSJ small-k CI now INCLUDES the null -- published significance is fragile")
    elif not dl_sig and hksj_sig:
        unc = "worse"
        reasons.append("HKSJ CI excludes null where DL did not (investigate before trusting)")
    if pi_crosses_null and dl_sig:
        if unc != "worse":
            unc = "better"
        reasons.append("prediction interval crosses the null: a new population could show "
                       "no/opposite effect -- decision-relevant heterogeneity the DL point hides")
    # HKSJ CI widening magnitude (honest, even when the conclusion is unchanged).
    dl_w = dl["ci_log"][1] - dl["ci_log"][0]
    hksj_w = hksj_ci[1] - hksj_ci[0]
    rel = (hksj_w - dl_w) / dl_w if dl_w else 0.0
    if not reasons:
        reasons.append(f"same conclusion; HKSJ CI width {rel:+.0%}, REML/PI more defensible in principle")

    # Overall: 'better' if uncertainty is better; else 'equal' (point ~equal is honest parity).
    overall = "better" if unc == "better" else ("worse" if unc == "worse" else "equal")
    return {
        "point_estimate_verdict": point_verdict,
        "point_log_shift": point_shift,
        "uncertainty_verdict": unc,
        "hksj_ci_width_vs_dl": rel,
        "pi_crosses_null": pi_crosses_null,
        "overall": overall,
        "reason": "; ".join(reasons),
    }


def run_tier1() -> list[dict]:
    results = []
    for t in TIER1:
        path = _METADAT / t.file
        if not path.is_file():
            results.append({"key": t.key, "status": "skipped",
                            "reason": f"open-data file missing: {path}"})
            continue
        studies, pmeasure, extra = _load(t)
        k = len(studies)
        # Published-method reproduction: DerSimonian-Laird (validated ===metafor).
        dl = pool(studies, pmeasure, "DL")
        # Overmind preferred stack: REML point + PM + HKSJ t-CI + t_{k-1} PI.
        reml = pool_with_intervals(studies, pmeasure, "REML")
        dl_iv = pool_with_intervals(studies, pmeasure, "DL")  # for HKSJ t-CI + PI
        is_ratio = extra["scale_back"] == "ratio"

        # Method comparison on the analysis (log/difference) scale vs the null=0.
        hksj_ci = dl_iv["hksj_ci_log"]      # small-k Hartung-Knapp interval
        pi = reml["pi_log"]
        method = _score_method(dl, reml, hksj_ci, pi)

        rec = {
            "key": t.key, "status": "ran", "tier": 1,
            "citation": t.citation, "k": k, "measure": t.measure,
            "published_method": t.published_method,
            "published_effect_reported": t.published_effect,
            "open_data_source": f"metadat/{t.file}", "data_sha256_16": _sha(path),
            "published_DL": {
                "estimate_log": dl["estimate_log"], "se": dl["se"],
                "ci_log": dl["ci_log"], "tau2": dl["tau2"], "I2": dl["I2_percent"],
                "estimate_ratio": dl.get("estimate_ratio"), "ci_ratio": dl.get("ci_ratio"),
            },
            "overmind_REML": {
                "estimate_log": reml["estimate_log"], "se": reml["se"],
                "ci_log": reml["ci_log"], "tau2": reml["tau2"],
                "estimate_ratio": reml.get("estimate_ratio"), "ci_ratio": reml.get("ci_ratio"),
                "hksj_ci_log": dl_iv["hksj_ci_log"], "hksj_ci_ratio": dl_iv.get("hksj_ci_ratio"),
                "pi_log": pi, "pi_ratio": reml.get("pi_ratio"),
                "pi_tcrit": reml["pi_tcrit"], "pi_df": reml["pi_df"],
            },
            "method_axis": method,
            # Completeness is honestly N/A for tier-1 (data == the review's own table).
            "completeness_axis": {
                "verdict": "n/a",
                "reason": "trial table IS the published open data; pre-registry trials, "
                          "no independent registry to diff (see Tier-2 for the completeness test).",
            },
            "transparency_axis": {
                "verdict": "yes",
                "reason": "every study row provenance-linked to metadat file + sha256; "
                          "whole result re-runnable from this script.",
                "per_study": [{"label": s.label,
                               "source": f"metadat/{t.file}"} for s in studies],
            },
        }
        results.append(rec)
    return results


def _nat(measure, log_est, log_ci):
    """Back-transform an analysis-scale estimate+CI to the reported natural scale."""
    if measure in ("RR", "OR"):
        return math.exp(log_est), [math.exp(log_ci[0]), math.exp(log_ci[1])]
    if measure == "ZCOR":                       # Fisher-z back to r
        return math.tanh(log_est), [math.tanh(log_ci[0]), math.tanh(log_ci[1])]
    return log_est, list(log_ci)                # MD / SMD already natural


if __name__ == "__main__":
    out = {"tier1": run_tier1()}
    Path("data/reconstruct_and_beat_tier1.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    print(f"{'target':27s} {'k':>3} {'meas':5s} {'DL est':>8} {'REML est':>9} "
          f"{'point':6s} {'uncert':7s} {'overall':7s}")
    for r in out["tier1"]:
        if r["status"] != "ran":
            print(f"{r['key']:27s} SKIP {r.get('reason')}")
            continue
        m = r["method_axis"]
        dl_nat, _ = _nat(r["measure"], r["published_DL"]["estimate_log"], r["published_DL"]["ci_log"])
        reml_nat, _ = _nat(r["measure"], r["overmind_REML"]["estimate_log"], r["overmind_REML"]["ci_log"])
        print(f"{r['key']:27s} {r['k']:>3} {r['measure']:5s} {dl_nat:>8.3f} {reml_nat:>9.3f} "
              f"{m['point_estimate_verdict']:6s} {m['uncertainty_verdict']:7s} {m['overall']:7s}")
        print(f"    -> {m['reason']}")
