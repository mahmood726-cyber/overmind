"""Tests for the meta-analysis verification benchmark (#2)."""
from __future__ import annotations

from overmind.intelligence.ma_verify import verify_rows


def _row(**kw):
    base = {
        "ma_id": "X", "k": "10", "theta": "-0.20",
        "se_std": "0.10", "se_hksj": "0.12", "se_ratio": "1.2",
        "ci_std_lo": "-0.40", "ci_std_hi": "0.00",      # touches null → not sig
        "ci_hksj_lo": "-0.44", "ci_hksj_hi": "0.04",
        "ci_width_ratio": "1.2", "p_std": "0.05", "p_hksj": "0.08",
        "sig_std": "FALSE", "sig_hksj": "FALSE", "conclusion_changed": "FALSE",
        "tau2": "0.01", "I2": "40",
    }
    base.update({k: str(v) for k, v in kw.items()})
    return base


def test_clean_row_no_violations():
    # default _row() is internally consistent (both non-significant, no change)
    r = verify_rows([_row()])
    assert r["status"] == "ok"
    assert r["total_violations"] == 0
    assert r["meta_analyses_checked"] == 1


def test_sig_flag_contradicts_ci():
    # sig_std TRUE but CI (-0.40, 0.05) includes 0 → contradiction flagged.
    r = verify_rows([_row(ci_std_lo="-0.40", ci_std_hi="0.05", sig_std="TRUE")])
    assert r["checks"]["sig_std_vs_ci"]["violations"] == 1


def test_conclusion_change_flag_wrong():
    # sig_std != sig_hksj but conclusion_changed says FALSE → flagged.
    r = verify_rows([_row(sig_std="TRUE", ci_std_lo="-0.40", ci_std_hi="-0.02",
                          sig_hksj="FALSE", conclusion_changed="FALSE")])
    assert r["checks"]["conclusion_change_flag"]["violations"] == 1


def test_i2_tau2_incoherent():
    r = verify_rows([_row(tau2="0.0", I2="55")])  # I²>0 but τ²=0
    assert r["checks"]["i2_tau2_coherence"]["violations"] == 1


def test_hksj_shrinkage_is_informative_not_violation():
    r = verify_rows([_row(se_std="0.12", se_hksj="0.10", se_ratio="0.8333",
                          ci_width_ratio="0.84")])
    assert r["informative"]["hksj_se_shrinkage"] == 1
