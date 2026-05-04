import sys, json
sys.path.insert(0, "src")
from lec.metaengine.statistics import calculate_meta_analysis_hksj

# Fixed 5-study deterministic input
studies = [
    {"estimate": 0.10, "se": 0.04},
    {"estimate": 0.15, "se": 0.05},
    {"estimate": 0.05, "se": 0.03},
    {"estimate": 0.20, "se": 0.06},
    {"estimate": 0.08, "se": 0.04},
]
r = calculate_meta_analysis_hksj(studies, use_hksj=True)
print(json.dumps({
    "pooled_estimate": round(r["pooled"]["estimate"], 6),
    "pooled_ci_low": round(r["pooled"]["ci_low"], 6),
    "pooled_ci_high": round(r["pooled"]["ci_high"], 6),
    "i2": round(r["heterogeneity"]["i2"], 4),
    "tau2": round(r["heterogeneity"]["tau2"], 6),
    "q": round(r["heterogeneity"]["q"], 4),
    "df": r["heterogeneity"]["df"],
    "pi_low": round(r["prediction_interval"]["pi_low"], 6),
    "pi_high": round(r["prediction_interval"]["pi_high"], 6),
    "hksj_ci_low": round(r["hksj_adjusted"]["ci_low"], 6),
    "hksj_ci_high": round(r["hksj_adjusted"]["ci_high"], 6),
    "n_studies": r["n_studies"],
}))