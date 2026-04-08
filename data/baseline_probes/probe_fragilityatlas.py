import sys, json, platform
platform._win32_ver = lambda *a, **k: ("10", "10.0.26100", "SP0", False)
platform._wmi_query = lambda *a, **k: "AMD64"
sys.path.insert(0, r"C:\FragilityAtlas")
import numpy as np
from src.estimators import meta_analysis

yi = np.array([0.5, 0.3, 0.8, 0.1, 0.6])
sei = np.array([0.1, 0.2, 0.15, 0.25, 0.12])
dl = meta_analysis(yi, sei, estimator="DL", ci_method="Wald")
reml_hksj = meta_analysis(yi, sei, estimator="REML", ci_method="HKSJ")
print(json.dumps({
    "dl_theta": round(float(dl.theta), 6),
    "dl_tau2": round(float(dl.tau2), 6),
    "dl_i2": round(float(dl.i2), 4),
    "reml_hksj_theta": round(float(reml_hksj.theta), 6),
    "reml_hksj_ci_lo": round(float(reml_hksj.ci_lo), 6),
    "reml_hksj_ci_hi": round(float(reml_hksj.ci_hi), 6),
}))