import sys, json
sys.path.insert(0, ".")
from overmind.discovery.analysis_signals import (
    detect_analysis_signals, compute_analysis_score, analysis_rigor_level,
    describe_analysis_signals, recommended_analysis_checks,
)
from overmind.verification.scope_lock import compute_tier

# Fixed deterministic input — README-style description with several signals
text = "Bayesian meta-analysis with HKSJ and DerSimonian-Laird random effects, MCMC convergence diagnostics, and bootstrap confidence intervals."
signals = detect_analysis_signals(text)
score = compute_analysis_score(signals, has_validation_history=True, has_oracle_benchmarks=False)
score_high = compute_analysis_score(signals, has_validation_history=True, has_oracle_benchmarks=True, has_drift_history=True)
labels = describe_analysis_signals(signals)
checks = recommended_analysis_checks(signals, score=score)

# Tier-derivation from risk + math
t1 = compute_tier("high", 12)        # 3 (most risk)
t2 = compute_tier("medium_high", 5)  # 2
t3 = compute_tier("low", 1)          # 1

print(json.dumps({
    "n_signals": len(signals),
    "signals": sorted(signals),
    "score": score,
    "score_with_oracle_drift": score_high,
    "rigor_at_default": analysis_rigor_level(score),
    "rigor_at_high": analysis_rigor_level(score_high),
    "n_labels": len(labels),
    "n_checks": len(checks),
    "tier_high_math12": t1,
    "tier_med_high_math5": t2,
    "tier_low_math1": t3,
}))