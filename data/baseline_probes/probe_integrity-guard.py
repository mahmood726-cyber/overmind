import sys, json
sys.path.insert(0, r"C:\Integrity-Guard-Forensics\src")
from baseline_balance_engine import welch_t_test, fisher_method

t, df, p = welch_t_test(10.0, 2.0, 50, 11.0, 2.5, 50)
chi2, k, combined_p = fisher_method([0.05, 0.01, 0.5, 0.03, 0.001])
print(json.dumps({
    "welch_t": round(t, 6),
    "welch_df": round(df, 4),
    "welch_p": round(p, 6),
    "fisher_chi2": round(chi2, 6),
    "fisher_k": k,
    "fisher_p": round(combined_p, 6),
}))