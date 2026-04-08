import sys, json
sys.path.insert(0, "shared")
from stats_utils import normal_cdf, normal_ppf_approx

cdf_196 = normal_cdf(1.96)
cdf_0 = normal_cdf(0.0)
cdf_neg = normal_cdf(-1.0)
ppf_975 = normal_ppf_approx(0.975)
ppf_50 = normal_ppf_approx(0.5)
ppf_025 = normal_ppf_approx(0.025)

print(json.dumps({
    "cdf_1.96": round(cdf_196, 6),
    "cdf_0.0": round(cdf_0, 6),
    "cdf_-1.0": round(cdf_neg, 6),
    "ppf_0.975": round(ppf_975, 6),
    "ppf_0.5": round(ppf_50, 6),
    "ppf_0.025": round(ppf_025, 6),
}))