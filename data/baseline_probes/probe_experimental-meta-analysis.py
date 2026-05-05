import sys, json
import numpy as np
sys.path.insert(0, ".")
from core_framework import MetaAnalysisData, DerSimonianLaird, REML, PauleMandel

# Fixed 6-study meta-analysis input — small enough to be deterministic
# across scipy versions but representative of a typical pooled estimand.
data = MetaAnalysisData(
    effect_sizes=np.array([0.30, 0.45, 0.20, 0.55, 0.35, 0.40]),
    variances=np.array([0.04, 0.05, 0.03, 0.06, 0.04, 0.05]),
)

dl = DerSimonianLaird().estimate(data)
reml = REML().estimate(data)
pm = PauleMandel().estimate(data)

print(json.dumps({
    "n_studies": data.n_studies,
    "dl_pooled": round(float(dl.pooled_effect), 6),
    "dl_se": round(float(dl.pooled_se), 6),
    "dl_tau2": round(float(dl.tau2), 6),
    "dl_i2": round(float(dl.i2), 4),
    "dl_q": round(float(dl.q_stat), 6),
    "reml_pooled": round(float(reml.pooled_effect), 6),
    "reml_tau2": round(float(reml.tau2), 6),
    "pm_pooled": round(float(pm.pooled_effect), 6),
    "pm_tau2": round(float(pm.tau2), 6),
}))