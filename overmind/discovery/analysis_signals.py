from __future__ import annotations

ADVANCED_ANALYSIS_PATTERNS: dict[str, tuple[str, ...]] = {
    "meta_analysis": (
        "meta-analysis",
        "meta analysis",
        "network meta",
        "meta-regression",
        "meta regression",
        "effect size",
        "heterogeneity",
        "forest plot",
        "pairwise",
    ),
    "survival_analysis": (
        "survival",
        "hazard ratio",
        "cox model",
        "cox proportional hazards",
        "kaplan-meier",
        "kaplan meier",
        "time-to-event",
        "time to event",
    ),
    "bayesian_modeling": (
        "bayesian",
        "bayes",
        "posterior",
        "credible interval",
        "mcmc",
        "hamiltonian monte carlo",
    ),
    "resampling": (
        "bootstrap",
        "jackknife",
        "monte carlo",
        "permutation test",
        "simulation study",
    ),
    "causal_inference": (
        "causal inference",
        "propensity score",
        "inverse probability weighting",
        "instrumental variable",
        "matching estimator",
        "sensitivity analysis",
    ),
    "diagnostic_accuracy": (
        "diagnostic odds ratio",
        "diagnostic accuracy",
        "sensitivity",
        "specificity",
        "roc curve",
        "auc",
        "likelihood ratio",
        "fagan",
    ),
    "hierarchical_modeling": (
        "hierarchical model",
        "multilevel model",
        "mixed effects",
        "mixed-effects",
        "random effects",
        "frailty model",
        "partial pooling",
    ),
    "calibration_validation": (
        "calibration",
        "discrimination",
        "brier score",
        "c-statistic",
        "c statistic",
        "concordance",
        "hosmer",
    ),
    "missing_data_imputation": (
        "missing data",
        "multiple imputation",
        "imputation",
        "mice",
        "inverse probability censoring",
    ),
    "optimization_numerics": (
        "newton-raphson",
        "newton raphson",
        "gradient descent",
        "optimization",
        "hessian",
        "eigenvalue",
        "positive definite",
        "cholesky",
    ),
}

ANALYSIS_SIGNAL_LABELS = {
    "meta_analysis": "meta-analysis",
    "survival_analysis": "survival analysis",
    "bayesian_modeling": "Bayesian modeling",
    "resampling": "resampling or simulation",
    "causal_inference": "causal inference",
    "diagnostic_accuracy": "diagnostic accuracy",
    "hierarchical_modeling": "hierarchical modeling",
    "calibration_validation": "calibration and validation",
    "missing_data_imputation": "missing data and imputation",
    "optimization_numerics": "numerical optimization",
}

ANALYSIS_SIGNAL_WEIGHTS = {
    "meta_analysis": 3,
    "survival_analysis": 3,
    "bayesian_modeling": 4,
    "resampling": 2,
    "causal_inference": 3,
    "diagnostic_accuracy": 3,
    "hierarchical_modeling": 3,
    "calibration_validation": 2,
    "missing_data_imputation": 2,
    "optimization_numerics": 2,
}


def detect_analysis_signals(text: str) -> list[str]:
    lowered = text.lower()
    signals: list[str] = []
    for signal, patterns in ADVANCED_ANALYSIS_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns):
            signals.append(signal)
    return signals


def describe_analysis_signals(signals: list[str]) -> list[str]:
    labels: list[str] = []
    for signal in signals:
        label = ANALYSIS_SIGNAL_LABELS.get(signal, signal.replace("_", " "))
        if label not in labels:
            labels.append(label)
    return labels


def compute_analysis_score(
    signals: list[str],
    *,
    has_validation_history: bool = False,
    has_oracle_benchmarks: bool = False,
    has_drift_history: bool = False,
) -> int:
    score = sum(ANALYSIS_SIGNAL_WEIGHTS.get(signal, 1) for signal in dict.fromkeys(signals))
    if has_validation_history:
        score += 1
    if has_oracle_benchmarks:
        score += 2
    if has_drift_history:
        score += 2
    return min(score, 20)


def analysis_rigor_level(score: int) -> str:
    if score >= 10:
        return "extreme"
    if score >= 6:
        return "high"
    if score >= 3:
        return "moderate"
    if score > 0:
        return "light"
    return "none"
