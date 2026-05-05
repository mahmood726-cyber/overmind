import sys, json
sys.path.insert(0, ".")
from asreview_5star.meta_analysis import pool_effects, eggers_test, heterogeneity_stats
from asreview_5star.irr import cohens_kappa, fleiss_kappa

# Fixed 5-study input
effects = [0.30, 0.45, 0.20, 0.55, 0.35]
ses     = [0.08, 0.10, 0.06, 0.12, 0.09]

re_dl   = pool_effects(effects, ses, model="random", method="DL")
fe      = pool_effects(effects, ses, model="fixed")

# Egger requires SEs and effects
egger = eggers_test(effects, ses)
het   = heterogeneity_stats(effects, ses)

# IRR — Cohen's kappa on a fixed 2-rater agreement matrix
ck = cohens_kappa(
    [1, 1, 0, 1, 0, 0, 1, 1, 0, 1],
    [1, 0, 0, 1, 1, 0, 1, 1, 0, 1],
)

print(json.dumps({
    "n_studies": len(effects),
    "re_dl_pooled": round(float(re_dl.pooled_effect), 6),
    "re_dl_ci_low": round(float(re_dl.ci_lower), 6),
    "re_dl_ci_high": round(float(re_dl.ci_upper), 6),
    "re_dl_tau2": round(float(re_dl.heterogeneity["tau_squared"]), 6),
    "re_dl_i2": round(float(re_dl.heterogeneity["I_squared"]), 4),
    "re_dl_q": round(float(re_dl.heterogeneity["Q"]), 6),
    "fe_pooled": round(float(fe.pooled_effect), 6),
    "het_q": round(float(het.get("Q") or het.get("q") or 0.0), 6) if isinstance(het, dict) else 0.0,
    "kappa": round(float(ck.coefficient), 6),
    "kappa_ci_low": round(float(ck.ci_lower), 6),
    "kappa_ci_high": round(float(ck.ci_upper), 6),
}))