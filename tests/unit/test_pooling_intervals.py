"""Tests for the additive prediction-interval / HKSJ t-CI layer.

Reference values are metafor 5.0.1 on metadat dat.bcg (validated in this session):
  DL logRR=-0.714117 se=0.178742 tau2=0.308760
  DL+KNHA CI = [-1.107821, -0.320413]
  manual Cochrane t_{k-1} PI = [-1.985896, 0.557662] (t_{12,.975}=2.178813)
"""
import math

import pytest

from overmind.evidence.pooling import Study, PoolingError
from overmind.evidence.pooling_intervals import pool_with_intervals, _t_quantile

# dat.bcg 2x2 (tpos,tneg,cpos,cneg) — the canonical high-heterogeneity RR set.
BCG = [
    (4, 119, 11, 128), (6, 300, 29, 274), (3, 228, 11, 209), (62, 13536, 248, 12619),
    (33, 5036, 47, 5761), (180, 1361, 372, 1079), (8, 2537, 10, 619), (505, 87886, 499, 87892),
    (29, 7470, 45, 7232), (17, 1699, 65, 1600), (186, 50448, 141, 27197), (5, 2493, 3, 2338),
    (27, 16886, 29, 17825),
]


def _bcg_studies():
    return [Study(label=str(i), ai=a, n1=a + b, ci=c, n2=c + d)
            for i, (a, b, c, d) in enumerate(BCG)]


def test_hksj_tci_matches_metafor_knha():
    r = pool_with_intervals(_bcg_studies(), "RR", "DL")
    lo, hi = r["hksj_ci_log"]
    assert lo == pytest.approx(-1.107821, abs=1e-4)
    assert hi == pytest.approx(-0.320413, abs=1e-4)
    # ratio-scale back-transform is present and consistent
    rl, rh = r["hksj_ci_ratio"]
    assert rl == pytest.approx(math.exp(lo), rel=1e-9)


def test_prediction_interval_is_cochrane_t_k_minus_1():
    r = pool_with_intervals(_bcg_studies(), "RR", "DL")
    assert r["pi_df"] == 12
    assert r["pi_tcrit"] == pytest.approx(2.178813, abs=1e-5)
    lo, hi = r["pi_log"]
    assert lo == pytest.approx(-1.985896, abs=1e-4)
    assert hi == pytest.approx(0.557662, abs=1e-4)
    # the PI is strictly WIDER than the Wald CI (it must contain more dispersion)
    ci_lo, ci_hi = r["ci_log"]
    assert lo < ci_lo and hi > ci_hi


def test_pi_wider_than_metafor_z_default_is_intentional():
    # Cochrane t_{k-1} PI is intentionally wider than metafor's z-default PI
    # ([-1.858154, 0.429919]); this encodes the more-honest small-sample rule.
    r = pool_with_intervals(_bcg_studies(), "RR", "DL")
    assert r["pi_log"][0] < -1.858154
    assert r["pi_log"][1] > 0.429919


def test_k2_pi_note_flags_single_df():
    # k=2 -> 1 d.f.; the note must warn (not silently emit a falsely-tight PI).
    studies = [Study(label="a", yi=math.log(0.86), vi=0.07 ** 2),
               Study(label="b", yi=math.log(0.87), vi=0.065 ** 2)]
    r = pool_with_intervals(studies, "HR", "REML")
    assert r["pi_df"] == 1
    assert "k==2" in r["pi_note"]


def test_reml_default_and_shape():
    r = pool_with_intervals(_bcg_studies(), "RR", "REML")
    assert r["method"] == "REML"
    assert r["estimate_log"] == pytest.approx(-0.714532, abs=1e-4)
    # REML path has no hksj_se (pool only emits it for DL/PM) -> no HKSJ CI key
    assert "hksj_ci_log" not in r


def test_t_quantile_guards_df():
    with pytest.raises(ValueError):
        _t_quantile(0, 0.05)
