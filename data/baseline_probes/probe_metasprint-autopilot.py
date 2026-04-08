import sys, json
sys.path.insert(0, "pipeline")
from pool_dl import pool_dl

r = pool_dl(
    effects=[0.5, 0.3, 0.8, 0.6, 0.4],
    variances=[0.04, 0.09, 0.06, 0.05, 0.08],
)
print(json.dumps({
    "theta": round(r["theta"], 6),
    "se": round(r["se"], 6),
    "ci_lo": round(r["ci_lo"], 6),
    "ci_hi": round(r["ci_hi"], 6),
    "tau2": round(r["tau2"], 6),
    "I2": round(r["I2"], 4),
    "Q": round(r["Q"], 6),
}))