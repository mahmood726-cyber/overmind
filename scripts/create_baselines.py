"""Generate numerical baselines for Overmind's NumericalWitness.

Creates baseline JSON files in data/baselines/{project_id}.json.
Each baseline contains a command, expected values, and tolerance.
The NumericalWitness runs the command, parses JSON output, and compares.

Usage:
    python scripts/create_baselines.py              # Create all baselines
    python scripts/create_baselines.py --dry-run    # Show what would be created
    python scripts/create_baselines.py --verify     # Create and immediately verify
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
BASELINES_DIR = DATA_DIR / "baselines"
PROBES_DIR = DATA_DIR / "baseline_probes"

PYTHON = sys.executable

# Each baseline spec: (project_id_prefix, project_path, probe_code, tolerance)
BASELINE_SPECS = [
    {
        "project_id_prefix": "metamethods",
        "project_path": r"C:\Models\MetaMethods",
        "tolerance": 1e-4,
        "probe": '''
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
''',
    },
    {
        "project_id_prefix": "advanced-nma-pooling",
        "project_path": r"C:\Projects\advanced-nma-pooling",
        "tolerance": 1e-4,
        "probe": '''
import sys, json
sys.path.insert(0, "src")
from nma_pool.data.builder import DatasetBuilder
from nma_pool.models.core_ad import ADNMAPooler
from nma_pool.models.spec import ModelSpec
from nma_pool.validation.simulation import simulate_continuous_abc_network

payload = simulate_continuous_abc_network()
dataset = DatasetBuilder().from_payload(payload)
fit = ADNMAPooler().fit(dataset, ModelSpec(
    outcome_id="efficacy", measure_type="continuous",
    reference_treatment="A", random_effects=True,
))
vals = {}
for t in ["B", "C"]:
    vals[f"effect_{t}"] = round(fit.treatment_effects[t], 6)
    vals[f"se_{t}"] = round(fit.treatment_ses[t], 6)
vals["tau"] = round(fit.tau, 6)
vals["n_studies"] = fit.n_studies
print(json.dumps(vals))
''',
    },
    {
        "project_id_prefix": "metasprint-autopilot",
        "project_path": r"C:\Projects\metasprint-autopilot",
        "tolerance": 1e-4,
        "probe": '''
import sys, json
sys.path.insert(0, "pipeline")
from pool_dl import pool_dl

r = pool_dl(
    effects=[0.5, 0.3, 0.8, 0.6, 0.4],
    variances=[0.04, 0.09, 0.06, 0.05, 0.08],
)
print(json.dumps({
    "theta": round(r["theta"], 6),
    "se": round(r["se"], 6),
    "ci_lo": round(r["ci_lo"], 6),
    "ci_hi": round(r["ci_hi"], 6),
    "tau2": round(r["tau2"], 6),
    "I2": round(r["I2"], 4),
    "Q": round(r["Q"], 6),
}))
''',
    },
    {
        "project_id_prefix": "saarc-e156-students",
        "project_path": r"C:\saarc-e156-students",
        "tolerance": 1e-6,
        "probe": '''
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
''',
    },
    {
        "project_id_prefix": "patientma",
        "project_path": r"C:\Models\PatientMA",
        "tolerance": 1e-4,
        "probe": '''
import sys, json
sys.path.insert(0, "shared")
from stats_utils import normal_cdf, normal_ppf_approx

cdf_196 = normal_cdf(1.96)
cdf_0 = normal_cdf(0.0)
cdf_neg = normal_cdf(-1.0)
ppf_975 = normal_ppf_approx(0.975)
ppf_50 = normal_ppf_approx(0.5)
ppf_025 = normal_ppf_approx(0.025)

print(json.dumps({
    "cdf_1.96": round(cdf_196, 6),
    "cdf_0.0": round(cdf_0, 6),
    "cdf_-1.0": round(cdf_neg, 6),
    "ppf_0.975": round(ppf_975, 6),
    "ppf_0.5": round(ppf_50, 6),
    "ppf_0.025": round(ppf_025, 6),
}))
''',
    },
    # ──────────────── Batch 2: 12 more projects ────────────────
    {
        "project_id_prefix": "metavoi",
        "project_path": r"C:\Models\MetaVoI",
        "tolerance": 1e-4,
        "probe": '''
import sys, json, platform
platform._win32_ver = lambda *a, **k: ("10", "10.0.26100", "SP0", False)
platform._wmi_query = lambda *a, **k: "AMD64"
sys.path.insert(0, r"C:\\Models\\MetaVoI")
import numpy as np
from metavoi.evpi import compute_evpi

draws = np.array([0.1, 0.2, 0.3, 0.15, 0.25, 0.35, 0.05, 0.4, 0.22, 0.18])
evpi_02 = compute_evpi(draws, mcid=0.2)
evpi_01 = compute_evpi(draws, mcid=0.1)
print(json.dumps({
    "evpi_mcid02": round(float(evpi_02), 6),
    "evpi_mcid01": round(float(evpi_01), 6),
    "draws_mean": round(float(np.mean(draws)), 6),
    "draws_std": round(float(np.std(draws)), 6),
}))
''',
    },
    {
        "project_id_prefix": "ubcma",
        "project_path": r"C:\ubcma",
        "tolerance": 1e-4,
        "probe": '''
import sys, json
sys.path.insert(0, r"C:\\ubcma\\src")
from ubcma.model import dersimonian_laird

yi = [0.5, 0.3, 0.8, 0.1, 0.6]
sei = [0.1, 0.2, 0.15, 0.25, 0.12]
result = dersimonian_laird(yi, sei)
print(json.dumps({
    "dl_mu": round(result["mu"], 6),
    "dl_tau": round(result["tau"], 6),
}))
''',
    },
    {
        "project_id_prefix": "metaaudit",
        "project_path": r"C:\MetaAudit",
        "tolerance": 1e-4,
        "probe": '''
import sys, json, platform
platform._win32_ver = lambda *a, **k: ("10", "10.0.26100", "SP0", False)
platform._wmi_query = lambda *a, **k: "AMD64"
sys.path.insert(0, r"C:\\MetaAudit")
import numpy as np
from metaaudit.recompute import compute_log_or, compute_smd

lor = compute_log_or(np.array([30]), np.array([100]), np.array([15]), np.array([100]))
smd = compute_smd(np.array([10.0]), np.array([2.0]), np.array([50]), np.array([8.0]), np.array([2.5]), np.array([50]))
print(json.dumps({
    "logOR": round(float(lor[0][0]), 6),
    "logOR_se": round(float(lor[1][0]), 6),
    "smd": round(float(smd[0][0]), 6),
    "smd_se": round(float(smd[1][0]), 6),
}))
''',
    },
    {
        "project_id_prefix": "truthcert-denominator",
        "project_path": r"C:\Models\truthcert-denominator-phase1",
        "tolerance": 1e-4,
        "probe": '''
import sys, json
sys.path.insert(0, r"C:\\Models\\truthcert-denominator-phase1")
from sim.meta_fixed import fixed_effect, random_effects_dl

yi = [0.5, 0.3, 0.8, 0.1, 0.6]
sei = [0.1, 0.2, 0.15, 0.25, 0.12]
fe = fixed_effect(yi, sei)
re = random_effects_dl(yi, sei)
print(json.dumps({
    "fe_mu": round(fe["mu"], 6),
    "fe_se": round(fe["se"], 6),
    "re_mu": round(re["mu"], 6),
    "re_tau2": round(re["tau2"], 6),
    "re_i2": round(re["I2"], 4),
}))
''',
    },
    {
        "project_id_prefix": "fragilityatlas",
        "project_path": r"C:\FragilityAtlas",
        "tolerance": 1e-4,
        "probe": '''
import sys, json, platform
platform._win32_ver = lambda *a, **k: ("10", "10.0.26100", "SP0", False)
platform._wmi_query = lambda *a, **k: "AMD64"
sys.path.insert(0, r"C:\\FragilityAtlas")
import numpy as np
from src.estimators import meta_analysis

yi = np.array([0.5, 0.3, 0.8, 0.1, 0.6])
sei = np.array([0.1, 0.2, 0.15, 0.25, 0.12])
dl = meta_analysis(yi, sei, estimator="DL", ci_method="Wald")
reml_hksj = meta_analysis(yi, sei, estimator="REML", ci_method="HKSJ")
print(json.dumps({
    "dl_theta": round(float(dl.theta), 6),
    "dl_tau2": round(float(dl.tau2), 6),
    "dl_i2": round(float(dl.i2), 4),
    "reml_hksj_theta": round(float(reml_hksj.theta), 6),
    "reml_hksj_ci_lo": round(float(reml_hksj.ci_lo), 6),
    "reml_hksj_ci_hi": round(float(reml_hksj.ci_hi), 6),
}))
''',
    },
    {
        "project_id_prefix": "metafrontierlab",
        "project_path": r"C:\MetaFrontierLab",
        "tolerance": 1e-3,
        "probe": '''
import sys, json, platform
platform._win32_ver = lambda *a, **k: ("10", "10.0.26100", "SP0", False)
platform._wmi_query = lambda *a, **k: "AMD64"
sys.path.insert(0, r"C:\\MetaFrontierLab")
import pandas as pd
from metafrontier.core import FrontierMetaAnalyzer

df = pd.DataFrame({
    "yi": [0.5, 0.3, 0.8, 0.1, 0.6],
    "sei": [0.1, 0.2, 0.15, 0.25, 0.12],
})
analyzer = FrontierMetaAnalyzer()
result = analyzer.fit(df, effect_col="yi", se_col="sei")
print(json.dumps({
    "estimate": round(float(result.estimate), 6),
    "std_error": round(float(result.std_error), 6),
    "tau": round(float(result.tau), 6),
}))
''',
    },
    {
        "project_id_prefix": "priorlab",
        "project_path": r"C:\Models\PriorLab",
        "tolerance": 1e-4,
        "probe": '''
import sys, json
sys.path.insert(0, r"C:\\Models\\PriorLab")
from priorlab.conjugate import normal_normal, beta_binomial

nn = normal_normal(mu0=0.0, sigma0=1.0, y=0.5, sigma_y=0.2)
bb = beta_binomial(a=1, b=1, x=7, n=10)
print(json.dumps({
    "nn_posterior_mean": round(nn["posterior_mean"], 6),
    "nn_posterior_sd": round(nn["posterior_sd"], 6),
    "bb_a_posterior": round(bb["a_posterior"], 6),
    "bb_b_posterior": round(bb["b_posterior"], 6),
    "bb_posterior_mean": round(bb["posterior_mean"], 6),
}))
''',
    },
    {
        "project_id_prefix": "africaforecast",
        "project_path": r"C:\Models\AfricaForecast",
        "tolerance": 1e-4,
        "probe": '''
import sys, json
sys.path.insert(0, r"C:\\Models\\AfricaForecast")
from engine.validate import compute_rmse, compute_mae, compute_coverage

actual = [1.0, 2.0, 3.0, 4.0, 5.0]
predicted = [1.1, 1.9, 3.2, 3.8, 5.1]
lo = [0.8, 1.6, 2.8, 3.5, 4.7]
hi = [1.4, 2.3, 3.5, 4.2, 5.4]
rmse = compute_rmse(actual, predicted)
mae = compute_mae(actual, predicted)
cov = compute_coverage(actual, lo, hi)
print(json.dumps({
    "rmse": round(rmse, 6),
    "mae": round(mae, 6),
    "coverage": round(cov, 6),
}))
''',
    },
    {
        "project_id_prefix": "gwam",
        "project_path": r"C:\Models\GWAM",
        "tolerance": 1e-4,
        "probe": '''
import sys, json
sys.path.insert(0, r"C:\\Models\\GWAM\\scripts")
from gwam_utils import normal_cdf, normal_quantile

cdf_196 = normal_cdf(1.96)
cdf_0 = normal_cdf(0.0)
ppf_975 = normal_quantile(0.975)
ppf_50 = normal_quantile(0.5)
print(json.dumps({
    "cdf_1.96": round(cdf_196, 6),
    "cdf_0.0": round(cdf_0, 6),
    "ppf_0.975": round(ppf_975, 6),
    "ppf_0.5": round(ppf_50, 6),
}))
''',
    },
    {
        "project_id_prefix": "metareproducer",
        "project_path": r"C:\MetaReproducer",
        "tolerance": 1e-4,
        "probe": '''
import sys, json
sys.path.insert(0, r"C:\\MetaReproducer")
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
''',
    },
    {
        "project_id_prefix": "integrity-guard",
        "project_path": r"C:\Integrity-Guard-Forensics",
        "tolerance": 1e-4,
        "probe": '''
import sys, json
sys.path.insert(0, r"C:\\Integrity-Guard-Forensics\\src")
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
''',
    },
]


def find_project_id(db_path: Path, prefix: str) -> str | None:
    """Look up the full project_id from the Overmind DB by prefix."""
    try:
        from overmind.storage.db import StateDatabase
        db = StateDatabase(db_path)
        for p in db.list_projects():
            if p.project_id.startswith(prefix):
                db.close()
                return p.project_id
        db.close()
    except Exception:
        pass
    return prefix


def create_baseline(spec: dict, dry_run: bool = False) -> dict | None:
    """Create a baseline JSON for one project. Returns the baseline dict or None on failure."""
    project_path = spec["project_path"]
    prefix = spec["project_id_prefix"]
    probe_code = spec["probe"].strip()
    tolerance = spec["tolerance"]

    # Write probe script
    PROBES_DIR.mkdir(parents=True, exist_ok=True)
    probe_path = PROBES_DIR / f"probe_{prefix}.py"
    probe_path.write_text(probe_code, encoding="utf-8")

    command = f"{PYTHON} {probe_path}"

    if dry_run:
        print(f"  Would create: {prefix}")
        print(f"    Command: {command}")
        print(f"    CWD: {project_path}")
        return None

    # Run the probe to capture expected values
    try:
        proc = subprocess.run(
            [PYTHON, str(probe_path)],
            cwd=project_path,
            capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT: {prefix}")
        return None

    if proc.returncode != 0:
        print(f"  FAIL: {prefix} — {proc.stderr.strip()[-200:]}")
        return None

    try:
        values = json.loads(proc.stdout.strip())
    except (json.JSONDecodeError, ValueError):
        print(f"  PARSE ERROR: {prefix} — output: {proc.stdout[:200]}")
        return None

    baseline = {
        "command": f"{PYTHON} {probe_path}",
        "values": values,
        "tolerance": tolerance,
        "project_path": project_path,
        "created_by": "create_baselines.py",
    }
    return baseline


def main() -> None:
    parser = argparse.ArgumentParser(description="Create numerical baselines")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify", action="store_true", help="Verify after creating")
    args = parser.parse_args()

    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    db_path = DATA_DIR / "state" / "overmind.db"

    print(f"Creating baselines for {len(BASELINE_SPECS)} projects")
    print()

    created = 0
    for spec in BASELINE_SPECS:
        prefix = spec["project_id_prefix"]
        project_id = find_project_id(db_path, prefix)

        print(f"[{prefix}]", end=" ")
        baseline = create_baseline(spec, dry_run=args.dry_run)

        if baseline is None:
            if not args.dry_run:
                print()
            continue

        # Save baseline
        baseline_path = BASELINES_DIR / f"{project_id}.json"
        baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
        n_values = len(baseline["values"])
        print(f"OK — {n_values} values, tolerance={baseline['tolerance']}")
        for key, val in baseline["values"].items():
            print(f"    {key}: {val}")
        created += 1

        # Optional immediate verify
        if args.verify:
            verify_proc = subprocess.run(
                [PYTHON, str(PROBES_DIR / f"probe_{prefix}.py")],
                cwd=spec["project_path"],
                capture_output=True, text=True, timeout=30,
            )
            if verify_proc.returncode == 0:
                actual = json.loads(verify_proc.stdout.strip())
                mismatches = []
                for key, expected in baseline["values"].items():
                    actual_val = actual.get(key)
                    if actual_val is None:
                        mismatches.append(f"{key}: missing")
                    elif isinstance(expected, (int, float)) and isinstance(actual_val, (int, float)):
                        if abs(actual_val - expected) > baseline["tolerance"]:
                            mismatches.append(f"{key}: {expected} vs {actual_val}")
                if mismatches:
                    print(f"    VERIFY FAIL: {', '.join(mismatches)}")
                else:
                    print(f"    VERIFY OK: {n_values}/{n_values} match")

    print()
    if args.dry_run:
        print(f"Dry run complete. Would create {len(BASELINE_SPECS)} baselines.")
    else:
        print(f"Created {created}/{len(BASELINE_SPECS)} baselines in {BASELINES_DIR}")


if __name__ == "__main__":
    main()
