import sys, json, platform
platform._win32_ver = lambda *a, **k: ("10", "10.0.26100", "SP0", False)
platform._wmi_query = lambda *a, **k: "AMD64"
sys.path.insert(0, ".")
import numpy as np
from metaaudit.recompute import pool_effects_reml

YI = [-0.889311, -1.585389, -1.348073, -1.441551, -0.217547, -0.786116,
      -1.620898, 0.011952, -0.469418, -1.371345, -0.339359, 0.445913, -0.017314]
VI = [0.325585, 0.194581, 0.415368, 0.02001, 0.05121, 0.006906, 0.223017,
      0.003962, 0.056434, 0.073025, 0.012412, 0.532506, 0.071405]
r = pool_effects_reml(np.array(YI), np.array(VI))
print(json.dumps({
    "k": r["k"],
    "estimate": round(r["estimate"], 6),
    "se": round(r["se"], 6),
    "tau2": round(r["tau2"], 6),
    "Q": round(r["Q"], 6),
    "I2": round(r["I2"], 4),
    "ci_lower": round(r["ci_lower"], 6),
    "ci_upper": round(r["ci_upper"], 6),
}))