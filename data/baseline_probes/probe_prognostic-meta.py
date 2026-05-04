import sys, json
import numpy as np
sys.path.insert(0, ".")
from core.meta import inverse_variance_pooling, random_effects_pooling
from core.stats import smith_transform, inv_smith_transform, smith_se, oe_transform

y = np.array([0.10, 0.15, 0.05, 0.20, 0.08])
se = np.array([0.04, 0.05, 0.03, 0.06, 0.04])
mu_fe, se_fe, _w = inverse_variance_pooling(y, se)
mu_re, se_re, tau2, q, df = random_effects_pooling(y, se)
sm = smith_transform(0.85)
inv_sm = inv_smith_transform(sm)
sm_se = smith_se(0.85, 0.02)
oe_log = oe_transform(1.5)
print(json.dumps({
    "fe_mu": round(float(mu_fe), 6),
    "fe_se": round(float(se_fe), 6),
    "re_mu": round(float(mu_re), 6),
    "re_se": round(float(se_re), 6),
    "re_tau2": round(float(tau2), 6),
    "re_q": round(float(q), 6),
    "re_df": int(df),
    "smith_logit_0_85": round(float(sm), 6),
    "smith_inv_roundtrip": round(float(inv_sm), 6),
    "smith_se_at_0_85": round(float(sm_se), 6),
    "oe_log_1_5": round(float(oe_log), 6),
}))