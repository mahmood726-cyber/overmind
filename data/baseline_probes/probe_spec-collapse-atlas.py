import sys, json
sys.path.insert(0, ".")
from spec_collapse import DATASETS
from spec_collapse.engine import re_pool, tau2_dl, tau2_reml

# Fixed dataset: metadat dat.bcg (13 studies, log-RR). Metafor canonical:
# REML tau2=0.3132, est=-0.7145, SE=0.1798 (pooled var=0.0323); DL tau2=0.3088.
d = DATASETS["bcg"]
yi, vi = d["yi"], d["vi"]
reml = tau2_reml(yi, vi)
dl = tau2_dl(yi, vi)
est, pooled_var = re_pool(yi, vi, reml)[:2]
print(json.dumps({
    "bcg_k": len(yi),
    "tau2_reml": round(reml, 6),
    "tau2_dl": round(dl, 6),
    "reml_est": round(est, 6),
    "reml_pooled_var": round(pooled_var, 6),
}))