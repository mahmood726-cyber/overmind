import sys, json
import numpy as np
sys.path.insert(0, ".")
from core.validation import safe_exp, safe_log, logsumexp_mean, ensure_positive_definite

# Pure math (deterministic)
e = safe_exp(2.0)
l = safe_log(7.5)
lse_mean = logsumexp_mean(np.array([1.0, 2.0, 3.0, 4.0, 5.0]))

# Matrix conditioning — fixed 2x2
M = np.array([[2.0, 0.99], [0.99, 1.0]])
M_pd = ensure_positive_definite(M, epsilon=1e-8)

# Edge cases
e_huge = safe_exp(1000.0)   # clipped to exp(700)
l_zero = safe_log(0.0)       # clipped to log(1e-300)

print(json.dumps({
    "exp_2": round(float(e), 6),
    "log_7_5": round(float(l), 6),
    "lse_mean_1_5": round(float(lse_mean), 6),
    "M_pd_diag0": round(float(M_pd[0, 0]), 6),
    "M_pd_diag1": round(float(M_pd[1, 1]), 6),
    "M_pd_off_diag": round(float(M_pd[0, 1]), 6),
    "exp_huge_clipped": round(float(e_huge), 0),
    "log_zero_clipped": round(float(l_zero), 4),
}))