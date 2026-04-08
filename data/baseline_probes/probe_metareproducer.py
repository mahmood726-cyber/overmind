import sys, json
sys.path.insert(0, r"C:\MetaReproducer")
from pipeline.meta_engine import pool_dl, pool_reml

yi = [0.5, 0.3, 0.8, 0.1, 0.6]
sei = [0.1, 0.2, 0.15, 0.25, 0.12]
dl = pool_dl(yi, sei)
reml = pool_reml(yi, sei)
print(json.dumps({
    "dl_pooled": round(dl["pooled"], 6),
    "dl_tau2": round(dl["tau2"], 6),
    "reml_pooled": round(reml["pooled"], 6),
    "reml_tau2": round(reml["tau2"], 6),
}))