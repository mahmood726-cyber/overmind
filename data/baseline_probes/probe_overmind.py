import sys, json
sys.path.insert(0, ".")
from overmind.evidence.pooling import pool, Study

YI = [-0.889311, -1.585389, -1.348073, -1.441551, -0.217547, -0.786116,
      -1.620898, 0.011952, -0.469418, -1.371345, -0.339359, 0.445913, -0.017314]
VI = [0.325585, 0.194581, 0.415368, 0.02001, 0.05121, 0.006906, 0.223017,
      0.003962, 0.056434, 0.073025, 0.012412, 0.532506, 0.071405]
r = pool([Study(yi=y, vi=v) for y, v in zip(YI, VI)], measure="RR", method="REML")
print(json.dumps({
    "k": r["k"],
    "estimate_log": round(r["estimate_log"], 6),
    "se": round(r["se"], 6),
    "tau2": round(r["tau2"], 6),
    "Q": round(r["Q"], 6),
    "I2_percent": round(r["I2_percent"], 4),
    "estimate_ratio": round(r["estimate_ratio"], 6),
}))