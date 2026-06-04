"""Deterministic, stdlib-only meta-analysis pooling on the log scale.

This is the from-scratch pooling engine the system previously lacked: ma_verify.py
VERIFIES pre-computed pooled tables, but nothing here POOLED raw study data into a
pooled estimate. The gold-standard benchmark (gold_benchmark.py) needs an actual
estimator to measure output-correctness against published reviews — this is it.

Design (per the advanced-stats rules, which this implements as code):
  - Always pool on the LOG scale (logRR/logOR), back-transform after — natural-scale
    + random effects gives Simpson's-paradox artefacts.
  - Zero-cell continuity correction adds 0.5 ONLY when >=1 cell of a study is zero
    (unconditional correction biases the OR toward 1).
  - Random-effects tau^2: DerSimonian-Laird (closed form) is fine for k>=10; for
    small k use Paule-Mandel (PM, iterative) — never DL for k<10.
  - I^2 = max(0, (Q-(k-1))/Q); tau^2 and I^2 are mathematically co-zero.
  - Wald CI uses z (matches metafor's default normal CI, method REML/DL). HKSJ SE is
    provided separately with the Q<k-1 floor (max(1, q)); its t-CI is out of scope
    here (no stdlib inverse-t) and documented as such.

Deterministic and offline: no numpy, no RNG, no network. Same inputs -> same bits.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

_Z_975 = 1.959963984540054  # qnorm(0.975); matches metafor's default normal CI


class PoolingError(ValueError):
    """Raised on inputs that cannot be pooled (k<2, non-positive variance, etc.)."""


@dataclass(frozen=True)
class Study:
    """One study's effect on the analysis (log) scale, or a binary 2x2.

    Provide EITHER (yi, vi) directly, OR a 2x2 (ai, n1, ci, n2) with `measure`.
    """
    label: str = ""
    yi: float | None = None          # effect on the log scale (logRR/logOR)
    vi: float | None = None          # variance of yi
    ai: int | None = None            # events, treatment arm
    n1: int | None = None            # total, treatment arm
    ci: int | None = None            # events, control arm
    n2: int | None = None            # total, control arm


def _binary_effect(ai, n1, ci, n2, measure: str) -> tuple[float, float]:
    """logRR/logOR + variance from a 2x2. 0.5 correction iff a cell is zero."""
    bi, di = n1 - ai, n2 - ci
    if min(ai, bi, ci, di) < 0:
        raise PoolingError(f"2x2 has a negative cell: a={ai} b={bi} c={ci} d={di}")
    if min(ai, bi, ci, di) == 0:                     # conditional 0.5 correction
        ai, bi, ci, di = ai + 0.5, bi + 0.5, ci + 0.5, di + 0.5
        n1d, n2d = ai + bi, ci + di
    else:
        n1d, n2d = float(n1), float(n2)
    if measure == "RR":
        yi = math.log((ai / n1d) / (ci / n2d))
        vi = 1.0 / ai - 1.0 / n1d + 1.0 / ci - 1.0 / n2d
    elif measure == "OR":
        yi = math.log((ai * di) / (bi * ci))
        vi = 1.0 / ai + 1.0 / bi + 1.0 / ci + 1.0 / di
    else:
        raise PoolingError(f"measure must be 'RR' or 'OR', got {measure!r}")
    if vi <= 0:
        raise PoolingError(f"non-positive variance {vi} for study (degenerate 2x2)")
    return yi, vi


def _normalize(studies: list[Study], measure: str) -> tuple[list[float], list[float], list[str]]:
    ys, vs, labels = [], [], []
    for s in studies:
        if s.yi is not None and s.vi is not None:
            if s.vi <= 0:
                raise PoolingError(f"study {s.label!r} has non-positive variance {s.vi}")
            ys.append(float(s.yi)); vs.append(float(s.vi))
        elif None not in (s.ai, s.n1, s.ci, s.n2):
            yi, vi = _binary_effect(s.ai, s.n1, s.ci, s.n2, measure)
            ys.append(yi); vs.append(vi)
        else:
            raise PoolingError(f"study {s.label!r} has neither (yi,vi) nor a full 2x2")
        labels.append(s.label)
    return ys, vs, labels


def _fe(ys, vs) -> tuple[float, float]:
    w = [1.0 / v for v in vs]
    sw = math.fsum(w)
    theta = math.fsum(wi * yi for wi, yi in zip(w, ys)) / sw
    return theta, 1.0 / sw


def _q_stat(ys, vs, theta_fe) -> float:
    return math.fsum((1.0 / v) * (y - theta_fe) ** 2 for y, v in zip(ys, vs))


def _tau2_dl(ys, vs, theta_fe) -> float:
    k = len(ys)
    w = [1.0 / v for v in vs]
    sw, sw2 = math.fsum(w), math.fsum(wi * wi for wi in w)
    q = _q_stat(ys, vs, theta_fe)
    denom = sw - sw2 / sw
    if denom <= 0:
        return 0.0
    return max(0.0, (q - (k - 1)) / denom)


def _tau2_pm(ys, vs) -> float:
    """Paule-Mandel: solve sum w*(y-theta)^2 = k-1 for tau^2 (w=1/(v+tau2)).
    Iterative fixed point; preferred for small k (advanced-stats rule)."""
    k = len(ys)
    if k < 2:
        return 0.0
    tau2 = 0.0
    for _ in range(200):
        w = [1.0 / (v + tau2) for v in vs]
        sw = math.fsum(w)
        theta = math.fsum(wi * yi for wi, yi in zip(w, ys)) / sw
        gen_q = math.fsum(wi * (y - theta) ** 2 for wi, y in zip(w, ys))
        # derivative of gen_q wrt tau2 = -sum w^2 (y-theta)^2 (theta-deriv negligible)
        deriv = -math.fsum((wi ** 2) * (y - theta) ** 2 for wi, y in zip(w, ys))
        if deriv == 0:
            break
        step = (gen_q - (k - 1)) / deriv
        new = max(0.0, tau2 - step)
        if abs(new - tau2) < 1e-10:
            tau2 = new
            break
        tau2 = new
    return tau2


def _re(ys, vs, tau2) -> tuple[float, float]:
    w = [1.0 / (v + tau2) for v in vs]
    sw = math.fsum(w)
    theta = math.fsum(wi * yi for wi, yi in zip(w, ys)) / sw
    return theta, 1.0 / sw


def _hksj_se(ys, vs, tau2, theta_re) -> float:
    """Hartung-Knapp-Sidik-Jonkman SE with the Q<k-1 floor (max(1, q)), per the
    advanced-stats HKSJ-floor rule. (t-distribution CI omitted: no stdlib inverse-t.)"""
    k = len(ys)
    w = [1.0 / (v + tau2) for v in vs]
    sw = math.fsum(w)
    q = math.fsum(wi * (y - theta_re) ** 2 for wi, y in zip(w, ys)) / (k - 1)
    return math.sqrt(max(1.0, q) / sw)


def pool(studies: list[Study], measure: str = "RR", method: str = "DL") -> dict:
    """Pool studies on the log scale. ``method`` in {'FE','DL','PM'}.

    Returns logRR/logOR pooled estimate, SE, z-Wald CI, tau^2, Q, I^2, and the
    back-transformed ratio + CI. Deterministic; raises PoolingError on bad input.
    """
    ys, vs, labels = _normalize(studies, measure)
    k = len(ys)
    if k < 2:
        raise PoolingError(f"need k>=2 studies to pool, got {k}")

    theta_fe, var_fe = _fe(ys, vs)
    q = _q_stat(ys, vs, theta_fe)
    i2 = max(0.0, (q - (k - 1)) / q) * 100.0 if q > 0 else 0.0

    if method == "FE":
        tau2, theta, var = 0.0, theta_fe, var_fe
    else:
        tau2 = _tau2_pm(ys, vs) if method == "PM" else _tau2_dl(ys, vs, theta_fe)
        theta, var = _re(ys, vs, tau2)

    se = math.sqrt(var)
    lo, hi = theta - _Z_975 * se, theta + _Z_975 * se
    out = {
        "measure": measure,
        "method": method,
        "k": k,
        "estimate_log": theta,
        "se": se,
        "ci_log": [lo, hi],
        "tau2": tau2,
        "Q": q,
        "df": k - 1,
        "I2_percent": i2,
        "estimate_ratio": math.exp(theta),
        "ci_ratio": [math.exp(lo), math.exp(hi)],
        "labels": labels,
    }
    if method in ("DL", "PM") and k >= 2:
        out["hksj_se"] = _hksj_se(ys, vs, tau2, theta)
    return out
