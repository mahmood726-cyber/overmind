import sys, json
sys.path.insert(0, ".")
from dta_bivariate_reference import bivariate_dl_pool, BNP_HF_STUDIES

r = bivariate_dl_pool(BNP_HF_STUDIES)
print(json.dumps({
    "k": r["k"],
    "pooledSens": round(r["pooledSens"], 6),
    "pooledSpec": round(r["pooledSpec"], 6),
    "plr": round(r["plr"], 6),
    "nlr": round(r["nlr"], 6),
    "dor": round(r["dor"], 6),
    "I2_sens": round(r["I2_sens"], 4),
    "I2_spec": round(r["I2_spec"], 4),
    "tau2_spec": round(r["tau2_spec"], 6),
}))