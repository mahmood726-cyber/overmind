import sys, json
sys.path.insert(0, r"C:\Models\GWAM\scripts")
from gwam_utils import normal_cdf, normal_quantile

cdf_196 = normal_cdf(1.96)
cdf_0 = normal_cdf(0.0)
ppf_975 = normal_quantile(0.975)
ppf_50 = normal_quantile(0.5)
print(json.dumps({
    "cdf_1.96": round(cdf_196, 6),
    "cdf_0.0": round(cdf_0, 6),
    "ppf_0.975": round(ppf_975, 6),
    "ppf_0.5": round(ppf_50, 6),
}))