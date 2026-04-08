import sys, json
sys.path.insert(0, r"C:\Models\truthcert-denominator-phase1")
from sim.meta_fixed import fixed_effect, random_effects_dl

yi = [0.5, 0.3, 0.8, 0.1, 0.6]
sei = [0.1, 0.2, 0.15, 0.25, 0.12]
fe = fixed_effect(yi, sei)
re = random_effects_dl(yi, sei)
print(json.dumps({
    "fe_mu": round(fe["mu"], 6),
    "fe_se": round(fe["se"], 6),
    "re_mu": round(re["mu"], 6),
    "re_tau2": round(re["tau2"], 6),
    "re_i2": round(re["I2"], 4),
}))