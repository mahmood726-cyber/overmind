import sys, json
sys.path.insert(0, r"C:\Models\PriorLab")
from priorlab.conjugate import normal_normal, beta_binomial

nn = normal_normal(mu0=0.0, sigma0=1.0, y=0.5, sigma_y=0.2)
bb = beta_binomial(a=1, b=1, x=7, n=10)
print(json.dumps({
    "nn_posterior_mean": round(nn["posterior_mean"], 6),
    "nn_posterior_sd": round(nn["posterior_sd"], 6),
    "bb_a_posterior": round(bb["a_posterior"], 6),
    "bb_b_posterior": round(bb["b_posterior"], 6),
    "bb_posterior_mean": round(bb["posterior_mean"], 6),
}))