import sys, json
sys.path.insert(0, ".")
from advanced_methods import (evalue, doi_plot_lfk, rosenthal_failsafe_n,
    quality_effects_model, proportion_meta, permutation_test_heterogeneity)

ev = evalue(2.0)
lfk = doi_plot_lfk([0.5, 0.8, 1.2], [0.1, 0.2, 0.15])
fsn = rosenthal_failsafe_n([0.5, 0.8, 1.2], [0.1, 0.2, 0.15])
qem = quality_effects_model([0.5, 0.8, 1.2], [0.1, 0.2, 0.15], [0.8, 0.6, 0.9])
pm = proportion_meta([10, 20, 30], [100, 200, 300])
pq = permutation_test_heterogeneity([0.5, 0.8, 1.2], [0.1, 0.2, 0.15], n_perm=999, seed=42)

print(json.dumps({
    "evalue_point": round(ev["evalue_point"], 6),
    "lfk_index": round(lfk["lfk_index"], 6),
    "failsafe_n": fsn,
    "qem_theta": round(qem["theta"], 6),
    "qem_se": round(qem["se"], 6),
    "proportion_pooled": round(pm["pooled_proportion"], 6),
    "permutation_p": round(pq["p_perm"], 4),
    "q_observed": round(pq["q_observed"], 4),
}))