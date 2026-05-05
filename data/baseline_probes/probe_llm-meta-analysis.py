import sys, json
import numpy as np
sys.path.insert(0, ".")
from evaluation.statistical_framework_v2 import AdvancedMetaAnalysis

# Fixed 6-study meta-analysis input
effects   = np.array([0.30, 0.45, 0.20, 0.55, 0.35, 0.40])
variances = np.array([0.04, 0.05, 0.03, 0.06, 0.04, 0.05])

# DerSimonian-Laird with Wald CI (force off-auto for stable behaviour)
res_dl = AdvancedMetaAnalysis.random_effects_analysis(
    effects, variances, tau2_method="DL", ci_method="wald", prediction=False,
)
# REML
res_reml = AdvancedMetaAnalysis.random_effects_analysis(
    effects, variances, tau2_method="REML", ci_method="wald", prediction=False,
)

print(json.dumps({
    "n_studies": len(effects),
    "dl_pooled":  round(float(res_dl.pooled_effect), 6),
    "dl_ci_low":  round(float(res_dl.ci.lower), 6),
    "dl_ci_high": round(float(res_dl.ci.upper), 6),
    "dl_tau2":    round(float(res_dl.tau_squared), 6),
    "dl_i2":      round(float(res_dl.heterogeneity.i_squared), 4),
    "dl_q":       round(float(res_dl.heterogeneity.q_statistic), 6),
    "dl_z":       round(float(res_dl.z_statistic), 4),
    "reml_pooled": round(float(res_reml.pooled_effect), 6),
    "reml_tau2":   round(float(res_reml.tau_squared), 6),
}))