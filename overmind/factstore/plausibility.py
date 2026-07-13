"""Deterministic, offline numeric-plausibility gate (āfāq — external consistency).

The fact store's provenance/taint layer is INTERNAL consistency (where did this
number come from). This is the EXTERNAL check: does the number look like it came
from the world? The DTA70 tell was not its provenance — it was that a sensitivity
range of 0.046 across 17 real diagnostic studies is IMPOSSIBLE. A human
diagnostician sees it instantly; nothing in the system did.

Tier-1, no model, no network. Each rule fires on whatever fields a fact's value
carries (a scalar, or a dict of meta-analysis fields). A fact that fails is FLAGGED
(recorded, never silently dropped) and CANNOT be consumed as verified.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

# A near-zero between-study spread across MANY studies is the DTA70 signature. For a
# proportion metric (sensitivity/specificity), a range this tight across >= this many
# studies is implausible — real diagnostic studies disagree more than this.
DISPERSION_MIN_K = 10
DISPERSION_TIGHT_RANGE = 0.05

# Effect ratios (HR/OR/RR). Two tiers, because 8.6 is extreme-but-possible while 500
# is impossible: <= 0 or outside the HARD band is a violation (blocks verify); outside
# the SOFT band but inside the hard band is a WARNING (surfaced for review, e.g. an
# HR of 8.6 — caught once by luck — gets eyeballed, not auto-rejected).
EFFECT_HARD_LOW, EFFECT_HARD_HIGH = 0.01, 100.0
EFFECT_SOFT_LOW, EFFECT_SOFT_HIGH = 0.2, 5.0

_PROPORTION_KEYS = ("sensitivity", "specificity", "se", "sp", "proportion",
                    "prevalence", "ppv", "npv")
_EFFECT_KEYS = ("hr", "or", "rr", "ratio", "effect")
_PROBABILITY_TOKENS = frozenset({"proportion", "probability", "p", "pvalue", "prob"})
_TOL = 1e-6

# The scalar ``kind`` hint is matched by WORD TOKEN, never raw substring. A substring
# match wrongly fires the effect-band rule on a count whose key merely CONTAINS an
# effect string — "or" inside "c[or]pus", "rr" inside "e[rr]or", "se" inside "u[se]d" —
# which would block legitimate real numbers and undermine the gate. Dict fields are
# already matched exactly (``lk in _PROPORTION_KEYS``); this only tightens the hint.
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _kind_tokens(kind: str | None) -> set[str]:
    return set(_TOKEN_RE.findall((kind or "").lower()))


def _kind_is_proportion(kind: str | None) -> bool:
    toks = _kind_tokens(kind)
    return bool(toks & set(_PROPORTION_KEYS)) or bool(toks & _PROBABILITY_TOKENS)


def _kind_is_effect(kind: str | None) -> bool:
    return bool(_kind_tokens(kind) & set(_EFFECT_KEYS))


@dataclass(slots=True)
class PlausibilityResult:
    ok: bool                                    # False iff there is a HARD violation
    violations: list[str] = field(default_factory=list)   # hard — block verification
    warnings: list[str] = field(default_factory=list)     # soft — surfaced, do not block

    def to_dict(self) -> dict:
        return {"ok": self.ok, "violations": list(self.violations),
                "warnings": list(self.warnings)}


def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)) and math.isfinite(v):
        return float(v)
    return None


def check_plausibility(value: Any, *, kind: str | None = None) -> PlausibilityResult:
    """Run every applicable tier-1 rule. Returns ok=False + the reasons on any hit.

    ``kind`` is an optional hint (e.g. "sensitivity", "hr", "proportion") used when
    ``value`` is a bare scalar; when ``value`` is a dict, rules key off field names.
    """
    v: list[str] = []
    w: list[str] = []
    d = value if isinstance(value, dict) else {}
    kl = (kind or "").lower()

    # -- scalar with a kind hint ------------------------------------------
    scalar = _num(value)
    if scalar is not None:
        if _kind_is_proportion(kl):
            if not (0.0 - _TOL <= scalar <= 1.0 + _TOL):
                v.append(f"{kind or 'proportion'}={scalar} outside [0,1]")
        if _kind_is_effect(kl):
            _effect_check(kind or "effect", scalar, v, w)

    # -- proportion fields in a dict --------------------------------------
    for key, val in d.items():
        n = _num(val)
        if n is None:
            continue
        lk = key.lower()
        if lk in _PROPORTION_KEYS and not (0.0 - _TOL <= n <= 1.0 + _TOL):
            v.append(f"{key}={n} outside [0,1] (a proportion cannot be)")
        if lk in ("p", "pvalue", "p_value") and not (0.0 - _TOL <= n <= 1.0 + _TOL):
            v.append(f"{key}={n} outside [0,1]")
        if lk in ("i2", "i_squared") and not (-_TOL <= n <= 100.0 + _TOL):
            v.append(f"I^2={n} outside [0,100]")
        if lk in ("tau2", "tau_squared") and n < -_TOL:
            v.append(f"tau^2={n} < 0 (a variance cannot be negative)")
        if lk in _EFFECT_KEYS:
            _effect_check(key, n, v, w)

    # -- CI must contain its own point estimate (the 1.53 [1.03-1.08] bug) -
    lo = _num(d.get("ci_low", d.get("ci_lower", d.get("lcl"))))
    hi = _num(d.get("ci_high", d.get("ci_upper", d.get("ucl"))))
    point = _num(d.get("point", d.get("estimate", d.get("effect", d.get("hr", d.get("or", d.get("rr")))))))
    if lo is not None and hi is not None:
        if lo > hi + _TOL:
            v.append(f"CI lower {lo} > upper {hi} (inverted interval)")
        if point is not None and not (lo - _TOL <= point <= hi + _TOL):
            v.append(f"point estimate {point} lies outside its own CI [{lo}, {hi}]")
        if abs(hi - lo) <= _TOL and point is not None:
            v.append(f"zero-width CI [{lo}, {hi}] — a real pooled estimate has uncertainty")

    # -- zero-variance pool ------------------------------------------------
    se = _num(d.get("se", d.get("std_err", d.get("standard_error"))))
    var = _num(d.get("variance", d.get("var")))
    if (se is not None and abs(se) <= _TOL and "sp" not in d and "specificity" not in d) or \
       (var is not None and abs(var) <= _TOL):
        v.append("zero-variance pooled estimate — impossible for a real synthesis")

    # -- 2x2 that doesn't sum to N ----------------------------------------
    a, b, c, e = (_num(d.get("a")), _num(d.get("b")), _num(d.get("c")), _num(d.get("d")))
    n = _num(d.get("n", d.get("total")))
    if None not in (a, b, c, e) and n is not None:
        if abs((a + b + c + e) - n) > 0.5:
            v.append(f"2x2 cells {a}+{b}+{c}+{e}={a+b+c+e} != N={n}")

    # -- counts vs reported effect (the 57/249 RapidMeta class) -----------
    v.extend(_counts_vs_effect(d))

    # -- impossible dispersion (the DTA70 signature) ----------------------
    v.extend(_dispersion_violations(d, kl))

    return PlausibilityResult(ok=not v, violations=v, warnings=w)


def _effect_check(name: str, x: float, v: list[str], w: list[str]) -> None:
    """<= 0 or astronomically large -> HARD violation; merely extreme -> WARNING."""
    if x <= 0:
        v.append(f"{name}={x} <= 0 (a ratio effect must be > 0)")
        return
    if not (EFFECT_HARD_LOW <= x <= EFFECT_HARD_HIGH):
        v.append(f"{name}={x} outside the possible ratio band "
                 f"[{EFFECT_HARD_LOW}, {EFFECT_HARD_HIGH}]")
        return
    if not (EFFECT_SOFT_LOW <= x <= EFFECT_SOFT_HIGH):
        w.append(f"{name}={x} is an extreme ratio (outside [{EFFECT_SOFT_LOW}, "
                 f"{EFFECT_SOFT_HIGH}]) — surface for review")


def _counts_vs_effect(d: dict) -> list[str]:
    et, nt = _num(d.get("events_t", d.get("events_treat"))), _num(d.get("n_t", d.get("n_treat")))
    ec, nc = _num(d.get("events_c", d.get("events_ctrl"))), _num(d.get("n_c", d.get("n_ctrl")))
    if None in (et, nt, ec, nc) or nt <= 0 or nc <= 0:
        return []
    if not (0 <= et <= nt and 0 <= ec <= nc):
        return [f"event counts out of range (events_t={et}/n_t={nt}, events_c={ec}/n_c={nc})"]
    reported = _num(d.get("rr")) or _num(d.get("risk_ratio"))
    if reported is None:
        return []
    rt, rc = et / nt, ec / nc
    if rc <= 0:
        return []
    computed = rt / rc
    if abs(computed - reported) > 0.05 * max(1.0, abs(reported)):
        return [f"reported RR={reported} contradicts counts (computed {computed:.3f} "
                f"from {et}/{nt} vs {ec}/{nc})"]
    return []


def _dispersion_violations(d: dict, kl: str) -> list[str]:
    k = _num(d.get("k", d.get("n_studies", d.get("studies"))))
    if k is None or k < DISPERSION_MIN_K:
        return []
    # observed spread: explicit range, or min/max, or from a values list, or 4*SD proxy
    rng = _num(d.get("range"))
    if rng is None:
        lo, hi = _num(d.get("min")), _num(d.get("max"))
        if lo is not None and hi is not None:
            rng = hi - lo
    if rng is None:
        vals = d.get("values")
        nums = [n for n in ( _num(x) for x in vals ) if n is not None] if isinstance(vals, (list, tuple)) else []
        if len(nums) >= 2:
            rng = max(nums) - min(nums)
    metric_is_proportion = _kind_is_proportion(kl) or \
        any(str(d.get("metric", "")).lower().startswith(p) for p in _PROPORTION_KEYS)
    if rng is not None and metric_is_proportion and rng < DISPERSION_TIGHT_RANGE:
        return [f"impossible dispersion: spread {rng} across k={int(k)} studies is "
                f"implausibly tight for a proportion (< {DISPERSION_TIGHT_RANGE}) — the "
                "DTA70 signature; real diagnostic studies disagree more than this"]
    return []
