import sys, json
import numpy as np
sys.path.insert(0, ".")
from mission_critical.diffmeta.engine import _python_pool

YI = np.array([-0.889311, -1.585389, -1.348073, -1.441551, -0.217547, -0.786116,
               -1.620898, 0.011952, -0.469418, -1.371345, -0.339359, 0.445913, -0.017314])
VI = np.array([0.325585, 0.194581, 0.415368, 0.02001, 0.05121, 0.006906, 0.223017,
               0.003962, 0.056434, 0.073025, 0.012412, 0.532506, 0.071405])
r = _python_pool(YI, VI, method="DL", measure="generic").to_dict()
print(json.dumps({
    "k": r["k"], "estimate": round(r["estimate"], 6), "se": round(r["se"], 6),
    "tau2": round(r["tau2"], 6), "i2": round(r["i2"], 4), "q": round(r["q"], 6),
}))