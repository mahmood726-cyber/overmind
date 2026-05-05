import sys, json
sys.path.insert(0, ".")
from moonshot_evidence_lab.advanced_meta import log_risk_ratio
from moonshot_evidence_lab.meta_analysis import run_meta_analysis
from moonshot_evidence_lab.models import StudyEffect

# Pure-math: log RR with 0.5 continuity correction on a fixed 2x2
log_rr, var = log_risk_ratio(15, 100, 25, 100)

# Meta-analysis on 4 fixed StudyEffect rows
effects = [
    StudyEffect(study_id="S1", label="Trial-1", effect_size=0.10, variance=0.0016),
    StudyEffect(study_id="S2", label="Trial-2", effect_size=0.15, variance=0.0025),
    StudyEffect(study_id="S3", label="Trial-3", effect_size=0.05, variance=0.0009),
    StudyEffect(study_id="S4", label="Trial-4", effect_size=0.20, variance=0.0036),
]
fe_result = run_meta_analysis(effects, model="fixed")
re_result = run_meta_analysis(effects, model="random", tau_method="dl")

print(json.dumps({
    "log_rr_15_100_25_100": round(float(log_rr), 6),
    "log_rr_var": round(float(var), 6),
    "fe_pooled": round(fe_result.pooled_effect, 6),
    "fe_se": round(fe_result.standard_error, 6),
    "fe_ci_low": round(fe_result.ci_low, 6),
    "fe_ci_high": round(fe_result.ci_high, 6),
    "re_pooled": round(re_result.pooled_effect, 6),
    "re_tau2": round(re_result.tau_squared, 6),
    "re_i2": round(re_result.i_squared, 4),
    "re_q": round(re_result.q, 6),
    "re_k": re_result.k,
    "re_h": round(re_result.h, 6),
}))