import sys, json
sys.path.insert(0, ".")
from golden.generate_references import pool

ds = json.load(open("golden/datasets/G01-homogeneous-small.json", encoding="utf-8"))
r = pool(ds["bus_payload"]["studies"])
fe, pm = r["fe"], r["re_pm"]
print(json.dumps({
    "k": r["k"],
    "fe_estimate": round(fe["estimate"], 8),
    "fe_se": round(fe["se"], 8),
    "pm_estimate": round(pm["estimate"], 8),
    "pm_se": round(pm["se"], 8),
    "pm_tau2": round(pm["tau2"], 8),
    "pm_qe": round(pm["qe"], 8),
    "pm_i2_pct": round(pm["i2_pct"], 6),
}))