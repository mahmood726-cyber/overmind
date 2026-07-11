"""Additive interval layer on top of the deterministic pooling core.

``pooling.pool`` is stdlib-only and deliberately omits two things it cannot do
without an inverse-t: the **prediction interval** (the range a *new* study's true
effect would plausibly fall in) and the **HKSJ t-CI** (Hartung-Knapp small-k
confidence interval). Both are exactly the methodological upgrades the
"reconstruct-and-beat" mission compares against a published DerSimonian-Laird
review, so they live here — a thin, purely additive wrapper. ``pool()`` itself is
untouched; this module only *reads* its output and adds two intervals.

Formulas (per the house advanced-stats rules):
  * Prediction interval: ``theta +/- t_{k-1, 1-alpha/2} * sqrt(tau^2 + se^2)`` —
    the Cochrane Handbook v6.5 form with ``t_{k-1}`` d.f. (matches metafor
    ``predict()`` v4+; IntHout-2016's ``t_{k-2}`` is superseded). Undefined for
    k<2 (pool() already enforces k>=2) and reported as such for k==2 where the
    single degree of freedom makes the interval very wide (honestly, not hidden).
  * HKSJ t-CI: ``theta_RE +/- t_{k-1, 1-alpha/2} * hksj_se`` where ``hksj_se``
    already carries the ``max(1, Q/(k-1))`` floor from ``pooling._hksj_se``.

Uses scipy only for the inverse-t quantile (deterministic). No RNG, no network.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.stats import t as _student_t

from overmind.evidence.pooling import Study, pool


def _t_quantile(df: int, alpha: float) -> float:
    """Two-sided ``1-alpha`` critical value from Student-t with ``df`` d.f."""
    if df < 1:
        raise ValueError(f"t-CI/PI needs df>=1 (k>=2), got df={df}")
    return float(_student_t.ppf(1.0 - alpha / 2.0, df))


@dataclass(frozen=True)
class Interval:
    lo: float
    hi: float
    scale: str  # "log"/"difference" analysis scale, or "ratio" (back-transformed)


def pool_with_intervals(studies: list[Study], measure: str = "RR",
                        method: str = "REML", alpha: float = 0.05) -> dict:
    """``pool()`` plus a prediction interval and (for DL/PM) an HKSJ t-CI.

    Returns the full ``pool()`` dict augmented with:
      * ``pi_log`` / ``pi_ratio``     — prediction interval (analysis scale + ratio)
      * ``pi_tcrit``, ``pi_df``       — the t critical value and d.f. used
      * ``hksj_ci_log`` / ``hksj_ci_ratio`` — HKSJ t-CI (present iff ``hksj_se`` is)
      * ``alpha``                     — the tail mass used (default 0.05 -> 95%)
    """
    base = pool(studies, measure=measure, method=method)
    k = base["k"]
    df = k - 1
    theta = base["estimate_log"]
    se = base["se"]
    tau2 = base["tau2"]
    is_ratio = base["scale"] == "ratio"

    tcrit = _t_quantile(df, alpha)

    # Prediction interval: total dispersion = between-study tau^2 + estimation se^2.
    sd_pred = math.sqrt(tau2 + se * se)
    pi_lo, pi_hi = theta - tcrit * sd_pred, theta + tcrit * sd_pred
    base["alpha"] = alpha
    base["pi_tcrit"] = tcrit
    base["pi_df"] = df
    base["pi_log"] = [pi_lo, pi_hi]
    base["pi_ratio"] = [math.exp(pi_lo), math.exp(pi_hi)] if is_ratio else None
    base["pi_note"] = ("k==2: prediction interval has 1 d.f. and is very wide; "
                       "reported honestly, not suppressed." if k == 2 else "")

    # HKSJ t-CI (only when pool() returned an hksj_se, i.e. DL/PM).
    hksj_se = base.get("hksj_se")
    if hksj_se is not None:
        h_lo, h_hi = theta - tcrit * hksj_se, theta + tcrit * hksj_se
        base["hksj_ci_log"] = [h_lo, h_hi]
        base["hksj_ci_ratio"] = [math.exp(h_lo), math.exp(h_hi)] if is_ratio else None

    return base
