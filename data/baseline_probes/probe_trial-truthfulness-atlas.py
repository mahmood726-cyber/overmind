import sys, json
sys.path.insert(0, "src")
from tta.meta import random_effects_pool

YI = [-0.889311, -1.585389, -1.348073, -1.441551, -0.217547, -0.786116,
      -1.620898, 0.011952, -0.469418, -1.371345, -0.339359, 0.445913, -0.017314]
VI = [0.325585, 0.194581, 0.415368, 0.02001, 0.05121, 0.006906, 0.223017,
      0.003962, 0.056434, 0.073025, 0.012412, 0.532506, 0.071405]
r = random_effects_pool(YI, VI)
print(json.dumps({
    "k": r.k, "mu": round(r.mu, 6), "tau2": round(r.tau2, 6),
    "ci_low": round(r.ci_low, 6), "ci_high": round(r.ci_high, 6),
}))