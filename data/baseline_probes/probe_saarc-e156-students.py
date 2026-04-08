import sys, json
sys.path.insert(0, "lib")
from stats_library import (gini_coefficient, shannon_entropy, spearman_correlation,
    linear_regression, cohens_d, odds_ratio)

gini_uniform = gini_coefficient([1, 1, 1, 1])
gini_skewed = gini_coefficient([1, 1, 1, 100])
shannon = shannon_entropy([0.25, 0.25, 0.25, 0.25])
spearman = spearman_correlation([1, 2, 3, 4, 5], [5, 4, 3, 2, 1])
lr = linear_regression([1, 2, 3, 4], [2, 5, 8, 11])
cd = cohens_d([10, 12, 14, 16, 18], [20, 22, 24, 26, 28])
orr = odds_ratio(10, 90, 20, 80)

print(json.dumps({
    "gini_uniform": round(gini_uniform["gini"], 6),
    "gini_skewed": round(gini_skewed["gini"], 6),
    "shannon_uniform": round(shannon["entropy"], 6) if isinstance(shannon, dict) else round(shannon, 6),
    "spearman_inverse": round(spearman["rho"], 6) if isinstance(spearman, dict) else round(spearman, 6),
    "linreg_slope": round(lr["slope"], 6),
    "linreg_intercept": round(lr["intercept"], 6),
    "linreg_r_squared": round(lr["r_squared"], 6),
    "cohens_d": round(cd["d"], 6) if isinstance(cd, dict) else round(cd, 6),
    "odds_ratio": round(orr["or"], 6) if isinstance(orr, dict) else round(orr, 6),
}))