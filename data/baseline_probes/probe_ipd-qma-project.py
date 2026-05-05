import sys, json
import numpy as np
sys.path.insert(0, ".")
from ipd_qma import IPDQMA, IQMAConfig

# Pin both numpy seed and config seed for full determinism
np.random.seed(42)
config = IQMAConfig(
    quantiles=[0.25, 0.5, 0.75],
    n_bootstrap=100,
    random_seed=42,
    show_progress=False,
)
analyzer = IPDQMA(config=config)

# Fixed 2-study input — small synthetic IPD with known shifts
np.random.seed(42)
study1_ctrl = np.random.normal(loc=0.0, scale=1.0, size=200)
study1_trt  = np.random.normal(loc=0.4, scale=1.0, size=200)
np.random.seed(43)
study2_ctrl = np.random.normal(loc=0.0, scale=1.0, size=200)
study2_trt  = np.random.normal(loc=0.5, scale=1.2, size=200)

# Pin seed before each analysis
np.random.seed(42)
res1 = analyzer.analyze_study(study1_ctrl, study1_trt)
np.random.seed(42)
res2 = analyzer.analyze_study(study2_ctrl, study2_trt)

# Quantile differences (control vs treatment) — round generously since
# bootstrap SEs vary slightly, but point estimates should be stable.
# Effects are arrays per quantile.
print(json.dumps({
    "n_quantiles": len(analyzer.quantiles),
    "quantiles": [round(q, 4) for q in analyzer.quantiles],
    "study1_q25_eff_bc": round(float(res1["quantile_effects_bc"][0]), 3),
    "study1_q50_eff_bc": round(float(res1["quantile_effects_bc"][1]), 3),
    "study1_q75_eff_bc": round(float(res1["quantile_effects_bc"][2]), 3),
    "study1_slope":      round(float(res1["slope"]), 3),
    "study1_n_control":   int(res1["n_control"]),
    "study1_n_treatment": int(res1["n_treatment"]),
    "study1_mean_diff":   round(float(res1["mean_treatment"]) - float(res1["mean_control"]), 3),
    "study2_slope":       round(float(res2["slope"]), 3),
}))