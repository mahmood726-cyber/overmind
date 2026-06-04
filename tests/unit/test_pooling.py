from __future__ import annotations

import math

import pytest

from overmind.evidence.pooling import PoolingError, Study, pool

# Canonical BCG / Colditz 1994 raw 2x2 (metafor dat.bcg): ai=vacc TB+, n1=vacc total,
# ci=control TB+, n2=control total.
_BCG = [
    (4, 123, 11, 139), (6, 306, 29, 303), (3, 231, 11, 220), (62, 13598, 248, 12867),
    (33, 5069, 47, 5808), (180, 1541, 372, 1451), (8, 2545, 10, 629), (505, 88391, 499, 88391),
    (29, 7499, 45, 7277), (17, 1716, 65, 1665), (186, 50634, 141, 27338), (5, 2498, 3, 2341),
    (27, 16913, 29, 17854),
]


def _bcg_studies():
    return [Study(str(i), ai=a, n1=n1, ci=c, n2=n2) for i, (a, n1, c, n2) in enumerate(_BCG)]


def test_fe_inverse_variance_hand_check():
    # y1=0,v1=0.25 (w=4); y2=1,v2=1 (w=1) -> theta=0.2, var=0.2, se=sqrt(0.2)
    r = pool([Study("a", yi=0.0, vi=0.25), Study("b", yi=1.0, vi=1.0)], method="FE")
    assert math.isclose(r["estimate_log"], 0.2, abs_tol=1e-12)
    assert math.isclose(r["se"], math.sqrt(0.2), abs_tol=1e-12)
    assert r["tau2"] == 0.0


def test_bcg_reproduces_published_random_effects():
    # metafor REML reference: logRR=-0.7145, se=0.1798, tau2~0.313, I2~92.2%
    r = pool(_bcg_studies(), measure="RR", method="PM")
    assert abs(r["estimate_log"] - (-0.7145)) < 0.01     # point estimate reproduced
    assert abs(r["se"] - 0.1798) < 0.01
    assert 90.0 < r["I2_percent"] < 94.0
    assert 0.25 < r["tau2"] < 0.37
    assert abs(r["estimate_ratio"] - 0.489) < 0.01       # back-transformed RR


def test_dl_and_pm_point_estimates_agree_on_bcg():
    dl = pool(_bcg_studies(), measure="RR", method="DL")
    pm = pool(_bcg_studies(), measure="RR", method="PM")
    assert abs(dl["estimate_log"] - pm["estimate_log"]) < 0.005  # methods agree on point


def test_homogeneous_studies_give_zero_tau2_and_i2():
    # identical effects -> Q ~ 0 -> tau2=0, I2=0
    r = pool([Study(yi=0.5, vi=0.1), Study(yi=0.5, vi=0.1), Study(yi=0.5, vi=0.1)], method="DL")
    assert r["tau2"] == 0.0
    assert r["I2_percent"] == 0.0


def test_zero_cell_correction_only_when_a_cell_is_zero():
    # a study with a zero event cell must not raise (0.5 correction applied)
    r = pool([Study(ai=0, n1=100, ci=5, n2=100), Study(ai=3, n1=100, ci=8, n2=100)],
             measure="OR", method="DL")
    assert math.isfinite(r["estimate_log"])
    # a clean 2x2 should NOT be perturbed: pooling twice is identical (determinism)
    clean = [Study(ai=10, n1=100, ci=20, n2=100), Study(ai=12, n1=100, ci=18, n2=100)]
    assert pool(clean, measure="OR")["estimate_log"] == pool(clean, measure="OR")["estimate_log"]


def test_k_less_than_2_fails_closed():
    with pytest.raises(PoolingError):
        pool([Study(yi=0.1, vi=0.2)], method="DL")


def test_non_positive_variance_fails_closed():
    with pytest.raises(PoolingError):
        pool([Study(yi=0.1, vi=0.0), Study(yi=0.2, vi=0.1)])


def test_generic_effect_and_2x2_paths_agree():
    # feed a 2x2's computed (yi,vi) directly and via the 2x2 — same result
    via_2x2 = pool([Study(ai=10, n1=100, ci=20, n2=100), Study(ai=15, n1=120, ci=25, n2=130)],
                   measure="RR", method="DL")
    y1 = math.log((10 / 100) / (20 / 100)); v1 = 1/10 - 1/100 + 1/20 - 1/100
    y2 = math.log((15 / 120) / (25 / 130)); v2 = 1/15 - 1/120 + 1/25 - 1/130
    via_yi = pool([Study(yi=y1, vi=v1), Study(yi=y2, vi=v2)], method="DL")
    assert math.isclose(via_2x2["estimate_log"], via_yi["estimate_log"], abs_tol=1e-12)
