"""Meta-analysis verification benchmark — operationalize the advanced-stats
rules as machine-checkable invariants over real meta-analysis result tables.

Given a CSV of per-MA pooled results (e.g. pairwise70's MA4_HKSJ_comparison.csv:
850 real Cochrane meta-analyses), check statistical invariants that a correct
synthesis MUST satisfy — and flag rows that violate them. This is the "verified
evidence synthesis" edge made measurable: no screening/extraction tool checks
whether the *statistics themselves* cohere.

Hard invariants (violations = likely error or data-integrity issue):
  - k >= 2; SE/τ² finite and non-negative
  - CI contains the point estimate (lo <= θ <= hi), both std and HKSJ
  - significance flag ⇔ CI excludes the null (0 on the log scale)
  - conclusion_changed ⇔ (sig_std != sig_hksj)
  - I²>0 ⇔ τ²>0 (heterogeneity coherence)
  - se_hksj > se_std ⇒ HKSJ CI is wider (ci_width_ratio > 1)
  - se_ratio == se_hksj/se_std (recomputed, tolerance)

Informative (not errors — surfaced for review, per the advanced-stats HKSJ-floor
and conclusion-instability rules):
  - HKSJ SE shrinkage (se_hksj < se_std)
  - conclusion changed between std and HKSJ

Stdlib only, deterministic, offline.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

_NULL = 0.0  # null effect on the log scale (logRR/logOR/logHR)


def _f(row: dict, key: str):
    v = (row.get(key) or "").strip()
    if v in ("", "NA", "NaN", "None"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _b(row: dict, key: str):
    v = (row.get(key) or "").strip().upper()
    if v in ("TRUE", "1"):
        return True
    if v in ("FALSE", "0"):
        return False
    return None


def _ci_excludes_null(lo, hi) -> bool:
    return not (lo <= _NULL <= hi)


def verify_rows(rows: list[dict], tol: float = 0.02) -> dict:
    checks = {
        "k_ge_2": 0, "finite_se_tau": 0, "ci_contains_theta": 0,
        "sig_std_vs_ci": 0, "sig_hksj_vs_ci": 0, "conclusion_change_flag": 0,
        "i2_tau2_coherence": 0, "hksj_ci_width": 0, "se_ratio_integrity": 0,
    }
    violations: dict[str, list[str]] = {k: [] for k in checks}
    n = 0
    hksj_shrinkage = 0
    conclusion_changed = 0

    def fail(check: str, mid: str):
        violations[check].append(mid)

    for row in rows:
        mid = row.get("ma_id") or row.get("analysis_id") or f"row{n}"
        theta = _f(row, "theta")
        se_std, se_hksj = _f(row, "se_std"), _f(row, "se_hksj")
        if theta is None or se_std is None or se_hksj is None:
            continue
        n += 1
        k = _f(row, "k")
        tau2, i2 = _f(row, "tau2"), _f(row, "I2")
        clo, chi = _f(row, "ci_std_lo"), _f(row, "ci_std_hi")
        hlo, hhi = _f(row, "ci_hksj_lo"), _f(row, "ci_hksj_hi")
        wr, sr = _f(row, "ci_width_ratio"), _f(row, "se_ratio")
        sig_std, sig_hksj = _b(row, "sig_std"), _b(row, "sig_hksj")
        cc = _b(row, "conclusion_changed")

        if k is not None:
            (checks.__setitem__("k_ge_2", checks["k_ge_2"] + 1) if k >= 2 else fail("k_ge_2", mid))
        ok_fin = se_std > 0 and se_hksj > 0 and (tau2 is None or tau2 >= -1e-9)
        checks["finite_se_tau"] += 1 if ok_fin else 0
        if not ok_fin:
            fail("finite_se_tau", mid)

        if None not in (clo, chi, hlo, hhi):
            ok_ci = (clo <= theta <= chi) and (hlo <= theta <= hhi)
            checks["ci_contains_theta"] += 1 if ok_ci else 0
            if not ok_ci:
                fail("ci_contains_theta", mid)
            if sig_std is not None:
                ok = (sig_std == _ci_excludes_null(clo, chi))
                checks["sig_std_vs_ci"] += 1 if ok else 0
                if not ok:
                    fail("sig_std_vs_ci", mid)
            if sig_hksj is not None:
                ok = (sig_hksj == _ci_excludes_null(hlo, hhi))
                checks["sig_hksj_vs_ci"] += 1 if ok else 0
                if not ok:
                    fail("sig_hksj_vs_ci", mid)

        if sig_std is not None and sig_hksj is not None and cc is not None:
            ok = (cc == (sig_std != sig_hksj))
            checks["conclusion_change_flag"] += 1 if ok else 0
            if not ok:
                fail("conclusion_change_flag", mid)
            if cc:
                conclusion_changed += 1

        if tau2 is not None and i2 is not None:
            # I² = τ²/(τ²+s²), so they're mathematically co-zero; near-zero values
            # differ only by rounding. Flag only GROSS incoherence: meaningful
            # heterogeneity on one metric but literally none on the other.
            # (I² here is on a percent scale.)
            gross = (i2 > 5.0 and tau2 <= 1e-9) or (tau2 > 1e-4 and i2 <= 1e-6)
            ok = not gross
            checks["i2_tau2_coherence"] += 1 if ok else 0
            if not ok:
                fail("i2_tau2_coherence", mid)

        if wr is not None and se_hksj > se_std:
            ok = wr > 1.0
            checks["hksj_ci_width"] += 1 if ok else 0
            if not ok:
                fail("hksj_ci_width", mid)
        if se_hksj < se_std:
            hksj_shrinkage += 1

        if sr is not None and se_std > 0:
            ok = abs(sr - se_hksj / se_std) <= tol
            checks["se_ratio_integrity"] += 1 if ok else 0
            if not ok:
                fail("se_ratio_integrity", mid)

    total_violations = sum(len(v) for v in violations.values())
    return {
        "meta_analyses_checked": n,
        "status": "ok" if total_violations == 0 else "violations",
        "total_violations": total_violations,
        "checks": {k: {"passed": checks[k], "violations": len(violations[k]),
                       "examples": violations[k][:5]} for k in checks},
        "informative": {
            "hksj_se_shrinkage": hksj_shrinkage,
            "conclusion_changed_std_vs_hksj": conclusion_changed,
        },
    }


def verify_csv(csv_path: str | Path, tol: float = 0.02) -> dict:
    path = Path(csv_path)
    if not path.exists():
        return {"error": f"not found: {path}"}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    result = verify_rows(rows, tol=tol)
    result["source"] = str(path)
    return result
