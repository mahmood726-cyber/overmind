"""Generate numerical baselines for Overmind's NumericalWitness.

<!-- sentinel:skip-file — project-path registry, absolute paths are the config data -->

Creates baseline JSON files in data/baselines/{project_id}.json.
Each baseline contains a command, expected values, and tolerance.
The NumericalWitness runs the command, parses JSON output, and compares.

This file is effectively a registry of canonical project locations on
Mahmood's machine — the absolute paths ARE the configuration data, not
leaks of deployment paths. Would ideally be a JSON registry but is kept
as inline Python for ergonomic `probe` string literals. Sentinel's
skip-file marker prevents it from flagging this as a hardcoded-path
violation.

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
        # Path repaired + probe upgraded 2026-06-05: was C:\MetaAudit (stale,
        # also hardcoded inside the probe); now C:\Projects\metaaudit with a
        # relative import. Baselines the REML recompute engine on canonical
        # dat.bcg (log-RR): reproduces metafor BCG (est within 5e-4, Q/I2 exact;
        # its own HKSJ-REML gives tau2=0.3181, est=-0.7150).
        "project_id_prefix": "metaaudit",
        "project_path": r"C:\Projects\metaaudit",
        "tolerance": 1e-4,
        "probe": '''
import sys, json, platform
platform._win32_ver = lambda *a, **k: ("10", "10.0.26100", "SP0", False)
platform._wmi_query = lambda *a, **k: "AMD64"
sys.path.insert(0, ".")
import numpy as np
from metaaudit.recompute import pool_effects_reml

YI = [-0.889311, -1.585389, -1.348073, -1.441551, -0.217547, -0.786116,
      -1.620898, 0.011952, -0.469418, -1.371345, -0.339359, 0.445913, -0.017314]
VI = [0.325585, 0.194581, 0.415368, 0.02001, 0.05121, 0.006906, 0.223017,
      0.003962, 0.056434, 0.073025, 0.012412, 0.532506, 0.071405]
r = pool_effects_reml(np.array(YI), np.array(VI))
print(json.dumps({
    "k": r["k"],
    "estimate": round(r["estimate"], 6),
    "se": round(r["se"], 6),
    "tau2": round(r["tau2"], 6),
    "Q": round(r["Q"], 6),
    "I2": round(r["I2"], 4),
    "ci_lower": round(r["ci_lower"], 6),
    "ci_upper": round(r["ci_upper"], 6),
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
    {
        "project_id_prefix": "metasprint-dose-response",
        "project_path": r"C:\Projects\metasprint-dose-response",
        "tolerance": 1e-6,
        "probe": '''
import sys, json, hashlib, re
from pathlib import Path
html_path = Path("metasprint-dose-response.html")
content = html_path.read_text(encoding="utf-8")
print(json.dumps({
    "size_kb": round(len(content.encode("utf-8")) / 1024, 1),
    "n_lines": content.count("\\n") + 1,
    "n_function_def": len(re.findall(r"function\\s+\\w+\\s*\\(", content)),
    "n_script_tag": len(re.findall(r"<script", content)),
    "n_div_tag": len(re.findall(r"<div", content)),
    "n_svg_tag": len(re.findall(r"<svg", content)),
    "content_hash_16": hashlib.sha256(content.encode("utf-8")).hexdigest()[:16],
}))
''',
    },
    {
        "project_id_prefix": "bayesian-ma",
        "project_path": r"C:\Models\BayesianMA",
        "tolerance": 1e-6,
        "probe": '''
import sys, json, hashlib, re
from pathlib import Path
html_path = Path("bayesian-ma.html")
content = html_path.read_text(encoding="utf-8")
print(json.dumps({
    "size_kb": round(len(content.encode("utf-8")) / 1024, 1),
    "n_lines": content.count("\\n") + 1,
    "n_function_def": len(re.findall(r"function\\s+\\w+\\s*\\(", content)),
    "n_script_tag": len(re.findall(r"<script", content)),
    "n_div_tag": len(re.findall(r"<div", content)),
    "content_hash_16": hashlib.sha256(content.encode("utf-8")).hexdigest()[:16],
}))
''',
    },
    {
        "project_id_prefix": "cardio-ctgov-living-meta-portfolio",
        "project_path": r"C:\Projects\cardio-ctgov-living-meta-portfolio",
        "tolerance": 1e-6,
        "probe": '''
import sys, json, hashlib, re
from pathlib import Path
html_path = Path("index.html")
content = html_path.read_text(encoding="utf-8")
print(json.dumps({
    "size_kb": round(len(content.encode("utf-8")) / 1024, 1),
    "n_lines": content.count("\\n") + 1,
    "n_function_def": len(re.findall(r"function\\s+\\w+\\s*\\(", content)),
    "n_script_tag": len(re.findall(r"<script", content)),
    "n_div_tag": len(re.findall(r"<div", content)),
    "content_hash_16": hashlib.sha256(content.encode("utf-8")).hexdigest()[:16],
}))
''',
    },
    {
        "project_id_prefix": "metasprintnma",
        "project_path": r"C:\Projects\metasprintnma",
        "tolerance": 1e-6,
        "probe": '''
import sys, json, hashlib, re
from pathlib import Path

# HTML structural invariants — count tags + functions + content hash.
# Stable as long as the app's HTML doesn't change.
html_path = Path("metasprint-nma.html")
content = html_path.read_text(encoding="utf-8")
size_kb = round(len(content.encode("utf-8")) / 1024, 1)
n_lines = content.count("\\n") + 1

# Count function definitions, script tags, key constructs
n_function = len(re.findall(r"function\\s+\\w+\\s*\\(", content))
n_arrow_func = len(re.findall(r"=>\\s*\\{", content))
n_script_tag = len(re.findall(r"<script", content))
n_div_tag = len(re.findall(r"<div", content))
n_svg_tag = len(re.findall(r"<svg", content))

content_hash_16 = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

print(json.dumps({
    "size_kb": size_kb,
    "n_lines": n_lines,
    "n_function_def": n_function,
    "n_arrow_func": n_arrow_func,
    "n_script_tag": n_script_tag,
    "n_div_tag": n_div_tag,
    "n_svg_tag": n_svg_tag,
    "content_hash_16": content_hash_16,
}))
''',
    },
    {
        "project_id_prefix": "finrenone",
        "project_path": r"C:\Projects\Finrenone",
        "tolerance": 1e-6,
        "probe": '''
import sys, json, importlib.util
from pathlib import Path
sys.path.insert(0, ".")

# Load scripts/audit_data_integrity.py via importlib (it imports
# defusedxml etc. that may print warnings; importlib avoids needing
# the scripts/ dir on sys.path).
spec = importlib.util.spec_from_file_location(
    "audit", str(Path("scripts") / "audit_data_integrity.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Pure-function probes on a fixed string fixture
sample_body = """trial1: {
    name: 'PARADIGM-HF', name: 'duplicate-name',
    pmid: 25176015, phase: 3, year: 2014, tE: 914,
    publishedHR: 0.80, hrLCI: 0.73, hrUCI: 0.87,
    sourceUrl: 'http://example.com',
    sourceUrl: 'http://duplicate.com',
    allOutcomes: [...]
}"""
dupes = mod.find_duplicate_fields(sample_body)
dupe_dict = {f: n for f, n in dupes}

print(json.dumps({
    "n_duplicates": len(dupes),
    "name_dup_count": dupe_dict.get("name", 0),
    "sourceUrl_dup_count": dupe_dict.get("sourceUrl", 0),
    "pmid_dup_count": dupe_dict.get("pmid", 0),
    "phase_dup_count": dupe_dict.get("phase", 0),
}))
''',
    },
    {
        "project_id_prefix": "kmcurve",
        "project_path": r"C:\Projects\KMcurve",
        "tolerance": 1e-6,
        "probe": '''
import sys, os, io, json
import contextlib
# detect_events_from_km has emoji prints at module import time. Redirect
# stdout to /dev/null during import so the JSON we emit is the only line.
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.insert(0, ".")
_real_stdout = sys.stdout
with contextlib.redirect_stdout(io.StringIO()):
    from detect_events_from_km import (
        detect_steps_in_km_curve, calculate_events_from_steps, infer_nrisk_times,
    )
sys.stdout = _real_stdout

# Fixed KM curve points: 5 vertical drops at known times
points = [
    (0.0, 1.00),
    (1.5, 1.00), (1.5, 0.95),
    (3.0, 0.95), (3.0, 0.85),
    (4.5, 0.85), (4.5, 0.75),
    (6.0, 0.75), (6.0, 0.60),
    (7.5, 0.60), (7.5, 0.50),
]
steps = detect_steps_in_km_curve(points, step_threshold=0.01)

# nrisk inference on a fixed sequence — 4 numbers across 8-month max
nrisk_times = infer_nrisk_times([100, 80, 60, 40], x_max=8.0)

# Event calculation with fixed initial nrisk
events = calculate_events_from_steps(steps, nrisk_times=[0.0, 4.0, 8.0], nrisk_values=[100, 80, 60])

print(json.dumps({
    "n_curve_points":  len(points),
    "n_steps_detected": len(steps),
    "first_step_time":  round(float(steps[0]["time"]), 6) if steps else None,
    "first_drop_mag":   round(float(steps[0]["drop_magnitude"]), 6) if steps else None,
    "total_drop":       round(float(sum(s["drop_magnitude"] for s in steps)), 6),
    "n_nrisk_times":    len(nrisk_times),
    "nrisk_t0":         round(float(nrisk_times[0]), 6) if nrisk_times else None,
    "nrisk_t_last":     round(float(nrisk_times[-1]), 6) if nrisk_times else None,
    "n_events":         len(events) if events else 0,
}))
''',
    },
    {
        "project_id_prefix": "llm-meta-analysis",
        "project_path": r"C:\Projects\llm-meta-analysis",
        "tolerance": 1e-4,
        "probe": '''
import sys, json
import numpy as np
sys.path.insert(0, ".")
from evaluation.statistical_framework_v2 import AdvancedMetaAnalysis

# Fixed 6-study meta-analysis input
effects   = np.array([0.30, 0.45, 0.20, 0.55, 0.35, 0.40])
variances = np.array([0.04, 0.05, 0.03, 0.06, 0.04, 0.05])

# DerSimonian-Laird with Wald CI (force off-auto for stable behaviour)
res_dl = AdvancedMetaAnalysis.random_effects_analysis(
    effects, variances, tau2_method="DL", ci_method="wald", prediction=False,
)
# REML
res_reml = AdvancedMetaAnalysis.random_effects_analysis(
    effects, variances, tau2_method="REML", ci_method="wald", prediction=False,
)

print(json.dumps({
    "n_studies": len(effects),
    "dl_pooled":  round(float(res_dl.pooled_effect), 6),
    "dl_ci_low":  round(float(res_dl.ci.lower), 6),
    "dl_ci_high": round(float(res_dl.ci.upper), 6),
    "dl_tau2":    round(float(res_dl.tau_squared), 6),
    "dl_i2":      round(float(res_dl.heterogeneity.i_squared), 4),
    "dl_q":       round(float(res_dl.heterogeneity.q_statistic), 6),
    "dl_z":       round(float(res_dl.z_statistic), 4),
    "reml_pooled": round(float(res_reml.pooled_effect), 6),
    "reml_tau2":   round(float(res_reml.tau_squared), 6),
}))
''',
    },
    {
        "project_id_prefix": "evidenceoracle",
        "project_path": r"C:\Models\EvidenceOracle",
        "tolerance": 1e-6,
        "probe": '''
import sys, json
sys.path.insert(0, ".")
import importlib.util
# assemble_features.py expects to find data files but we only need its helpers
spec = importlib.util.spec_from_file_location("eo_features", "assemble_features.py")
mod = importlib.util.module_from_spec(spec)

# Stub heavy IO so loading the module doesn't try to open absent CSVs
import builtins, types
class _Skip(Exception): pass
mod.__dict__["__name__"] = "eo_features"
spec.loader.exec_module(mod)

# compute_benford_mad on a fixed digit distribution.
# Benford-conforming → low MAD. Uniform → higher.
benford_like = [{"d1": d} for d in [1]*30 + [2]*18 + [3]*12 + [4]*10 + [5]*8 + [6]*7 + [7]*6 + [8]*5 + [9]*4]
uniform_like = [{"d1": d} for d in list(range(1, 10)) * 11]

mad_benford = mod.compute_benford_mad(benford_like)
mad_uniform = mod.compute_benford_mad(uniform_like)

# Empty / too-few inputs return NaN — skip emitting them (None breaks witness)
print(json.dumps({
    "n_benford_input": len(benford_like),
    "n_uniform_input": len(uniform_like),
    "mad_benford_like": round(float(mad_benford), 6),
    "mad_uniform_like": round(float(mad_uniform), 6),
    "uniform_higher_than_benford": bool(mad_uniform > mad_benford),
}))
''',
    },
    {
        "project_id_prefix": "evidenceforecast",
        "project_path": r"C:\Models\EvidenceForecast",
        "tolerance": 1e-6,
        "probe": '''
import sys, json
sys.path.insert(0, ".")
from evidence_forecast.representativeness import compute_representativeness
from evidence_forecast.constants import (
    SCHEMA_VERSION, FORECAST_HORIZON_MONTHS,
    PICO_REQUIRED_FIELDS, EFFECT_FIELDS, FLIP_FIELDS, REPRESENTATIVENESS_FIELDS,
    CARD_TOP_LEVEL_FIELDS,
)

# Fixed normalised weights — burden-weighted overlap is deterministic
trial_w  = {"USA": 0.50, "GBR": 0.30, "CAN": 0.20}
burden_w = {"IND": 0.40, "USA": 0.30, "GBR": 0.20, "CAN": 0.10}
res = compute_representativeness(trial_w, burden_w, source="aact")

# Empty trial weights → degenerate path
empty = compute_representativeness({}, burden_w)

print(json.dumps({
    "schema_version": SCHEMA_VERSION,
    "forecast_horizon_months": FORECAST_HORIZON_MONTHS,
    "n_pico_required": len(PICO_REQUIRED_FIELDS),
    "n_effect_fields": len(EFFECT_FIELDS),
    "n_flip_fields": len(FLIP_FIELDS),
    "n_card_top_level": len(CARD_TOP_LEVEL_FIELDS),
    "overlap_score": round(res.overlap_score, 6),
    "trial_country_count": res.trial_country_count,
    "burden_weighted": res.burden_weighted,
    "source_aact": res.source,
    "empty_overlap": empty.overlap_score,
    "empty_source": empty.source,
}))
''',
    },
    {
        "project_id_prefix": "globalst",
        "project_path": r"C:\Projects\globalst",
        "tolerance": 1e-6,
        "probe": '''
import sys, json
sys.path.insert(0, "src")
from model_stnma import generate_truthcert_hash
from ingest_data import fetch_ct_gov_data, fetch_ihme_burden, fetch_world_bank_covariates

# Pure SHA-256 over fixed JSON input
fixed = {"trial_id": "NCT001", "intervention": "A", "control": "B",
         "outcome": "mortality", "effect_size": 0.85, "n": 5000}
h = generate_truthcert_hash(fixed)

# Fixture-loading functions return the in-tree mock when fixtures are
# absent. Both deterministic.
ct = fetch_ct_gov_data()
ih = fetch_ihme_burden()
wb = fetch_world_bank_covariates()

print(json.dumps({
    "hash_64": h[:64],
    "hash_first_16": h[:16],
    "hash_len": len(h),
    "ctgov_n": len(ct) if isinstance(ct, list) else 1,
    "ihme_n":  len(ih) if isinstance(ih, list) else 1,
    "wb_n":    len(wb) if isinstance(wb, list) else 1,
}))
''',
    },
    {
        "project_id_prefix": "hta-evidence-integrity",
        "project_path": r"C:\Models\HTA_Evidence_Integrity_Suite",
        "tolerance": 1e-3,
        "probe": '''
import sys, json, csv, statistics
from pathlib import Path

# Read the canonical IAI output and emit class counts + summary stats.
# All deterministic: the CSV is checked into the repo per the manuscript.
ia_path = Path("analysis/output/information_adequacy/information_adequacy_FINAL.csv")
with ia_path.open(encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

iai_classes = {}
for r in rows:
    c = r["IAI_final_class"]
    iai_classes[c] = iai_classes.get(c, 0) + 1

iai_vals = [float(r["IAI_final"]) for r in rows if r["IAI_final"]]

print(json.dumps({
    "n_ma": len(rows),
    "adequate_count":   iai_classes.get("Adequate", 0),
    "marginal_count":   iai_classes.get("Marginal", 0),
    "inadequate_count": iai_classes.get("Inadequate", 0),
    "critical_count":   iai_classes.get("Critical", 0),
    "iai_mean":   round(statistics.mean(iai_vals), 4),
    "iai_median": round(statistics.median(iai_vals), 4),
    "iai_min":    round(min(iai_vals), 4),
    "iai_max":    round(max(iai_vals), 4),
}))
''',
    },
    {
        "project_id_prefix": "cardiooracle",
        "project_path": r"C:\Models\CardioOracle",
        "tolerance": 1e-6,
        "probe": '''
import sys, json
sys.path.insert(0, ".")
# Avoid importing heavy DB modules — load shared.py directly
import importlib.util
spec = importlib.util.spec_from_file_location("co_shared", "curate/shared.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Pure-string classifier probes — deterministic
drugs = [
    ("empagliflozin",   "sglt2_inhibitor"),
    ("Sacubitril/Valsartan 49/51 mg", "arni"),
    ("vericiguat",      "scg_stimulator"),
    ("placebo",         "other"),
    ("aspirin 81 mg",   "other"),
]
classified = [(n, e, mod.classify_drug(n)) for n, e in drugs]

endpoints = [
    "Cardiovascular death",
    "Heart failure hospitalization",
    "All-cause mortality",
    "MACE composite",
    "Quality of life (KCCQ)",
    "Random unrelated thing",
]
endpoint_ids = [mod.classify_endpoint(t) for t in endpoints]

print(json.dumps({
    "n_drug_cases": len(drugs),
    "drug_classifications": [c for _, _, c in classified],
    "n_endpoint_cases": len(endpoints),
    "endpoint_classifications": endpoint_ids,
    "drug_other_count": sum(1 for c in classified if c[2] == "other"),
    "endpoint_other_count": sum(1 for e in endpoint_ids if e == "other"),
}))
''',
    },
    {
        "project_id_prefix": "esc-acs-living-meta",
        "project_path": r"C:\Projects\esc-acs-living-meta",
        "tolerance": 1e-6,
        "probe": '''
import sys, json
sys.path.insert(0, ".")
from aact_local_gateway import (
    validate_sql, convert_postgres_placeholders, ALLOWED_QUERY_IDS, FORBIDDEN_SQL_TOKENS,
)

# validate_sql contract: returns (ok, reason). Several deterministic cases.
v_select = validate_sql("SELECT * FROM studies WHERE nct_id = $1")
v_insert = validate_sql("INSERT INTO studies VALUES ($1)")
v_update = validate_sql("UPDATE studies SET x = $1")
v_drop   = validate_sql("DROP TABLE studies")
v_select_with_drop_string = validate_sql("SELECT 'drop' FROM studies")  # should pass — keyword in literal

# Placeholder conversion: $1 → %s
sql_in = "SELECT * FROM x WHERE a = $1 AND b = $2"
sql_out, params_out = convert_postgres_placeholders(sql_in, ["foo", "bar"])

print(json.dumps({
    "v_select_ok":      v_select[0],
    "v_insert_ok":      v_insert[0],
    "v_update_ok":      v_update[0],
    "v_drop_ok":        v_drop[0],
    "v_select_drop_lit_ok": v_select_with_drop_string[0],
    "n_allowed_queries": len(ALLOWED_QUERY_IDS),
    "n_forbidden_tokens": len(FORBIDDEN_SQL_TOKENS),
    "sql_out": sql_out,
    "n_params_out": len(params_out),
}))
''',
    },
    {
        "project_id_prefix": "ipd-meta-pro-link",
        "project_path": r"C:\Projects\ipd-meta-pro-link",
        "tolerance": 1e-6,
        "probe": '''
import sys, json, hashlib
from pathlib import Path

# Module structure invariants — counts and aggregate hash of dev/modules.
# All deterministic given a fixed working tree.
modules_dir = Path("dev") / "modules"
assert modules_dir.is_dir(), f"missing {modules_dir}"

files = sorted(modules_dir.iterdir(), key=lambda p: p.name)
n_files = len(files)
n_html  = sum(1 for f in files if f.suffix == ".html")
n_js    = sum(1 for f in files if f.suffix == ".js")
n_other = n_files - n_html - n_js
total_size = sum(f.stat().st_size for f in files)

# Ordered concatenation hash (changes if any module changes)
h = hashlib.sha256()
for f in files:
    h.update(f.name.encode("utf-8"))
    h.update(b"|")
    h.update(str(f.stat().st_size).encode("ascii"))
    h.update(b";")
manifest_hash = h.hexdigest()[:16]

print(json.dumps({
    "n_modules": n_files,
    "n_html": n_html,
    "n_js": n_js,
    "n_other": n_other,
    "total_size_kb": round(total_size / 1024, 1),
    "first_module": files[0].name if files else "",
    "last_module":  files[-1].name if files else "",
    "manifest_hash_16": manifest_hash,
}))
''',
    },
    {
        # Path repaired + probe upgraded 2026-06-05: was C:\overmind (stale) with
        # a tier-logic probe; now baselines Overmind's OWN pooling engine (the
        # gold-benchmark reproduction engine) on the canonical metadat dat.bcg
        # (log-RR). Reproduces metafor EXACTLY: REML tau2=0.3132, est=-0.7145,
        # SE=0.1798 — the strongest possible external cross-check.
        "project_id_prefix": "overmind",
        "project_path": r"C:\Users\mahmo\code\overmind",
        "tolerance": 1e-4,
        "probe": '''
import sys, json
sys.path.insert(0, ".")
from overmind.evidence.pooling import pool, Study

YI = [-0.889311, -1.585389, -1.348073, -1.441551, -0.217547, -0.786116,
      -1.620898, 0.011952, -0.469418, -1.371345, -0.339359, 0.445913, -0.017314]
VI = [0.325585, 0.194581, 0.415368, 0.02001, 0.05121, 0.006906, 0.223017,
      0.003962, 0.056434, 0.073025, 0.012412, 0.532506, 0.071405]
r = pool([Study(yi=y, vi=v) for y, v in zip(YI, VI)], measure="RR", method="REML")
print(json.dumps({
    "k": r["k"],
    "estimate_log": round(r["estimate_log"], 6),
    "se": round(r["se"], 6),
    "tau2": round(r["tau2"], 6),
    "Q": round(r["Q"], 6),
    "I2_percent": round(r["I2_percent"], 4),
    "estimate_ratio": round(r["estimate_ratio"], 6),
}))
''',
    },
    {
        "project_id_prefix": "repo300-enma-snma",
        "project_path": r"C:\Projects\repo300-ENMA-SNMA",
        "tolerance": 1e-6,
        "probe": '''
import sys, json, importlib.util
from pathlib import Path
sys.path.insert(0, ".")

# repo300/R/03_simulation_engine.py has dataclass scenario factories; load
# the file directly since the dir name starts with a digit.
spec = importlib.util.spec_from_file_location(
    "sim_engine", str(Path("R") / "03_simulation_engine.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

baseline = mod.create_baseline_scenario()
sparse   = mod.create_sparse_network_scenario()
incons   = mod.create_inconsistency_scenario(magnitude=0.3)
hi_het   = mod.create_high_heterogeneity_scenario()
star     = mod.create_star_network_scenario()

print(json.dumps({
    "baseline_n_treatments": baseline.network.n_treatments,
    "baseline_n_studies":    baseline.network.n_studies,
    "baseline_connectivity": baseline.network.connectivity,
    "sparse_n_studies":      sparse.network.n_studies,
    "sparse_connectivity":   sparse.network.connectivity,
    "incons_magnitude":      0.3,
    "hi_het_connectivity":   hi_het.network.connectivity,
    "star_connectivity":     star.network.connectivity,
}))
''',
    },
    {
        "project_id_prefix": "ipd-qma-project",
        "project_path": r"C:\Projects\ipd_qma_project",
        "tolerance": 1e-3,
        "probe": '''
import sys, json
import numpy as np
sys.path.insert(0, ".")
from ipd_qma import IPDQMA, IQMAConfig

# Pin both numpy seed and config seed for full determinism
np.random.seed(42)
config = IQMAConfig(
    quantiles=[0.25, 0.5, 0.75],
    n_bootstrap=100,
    random_seed=42,
    show_progress=False,
)
analyzer = IPDQMA(config=config)

# Fixed 2-study input — small synthetic IPD with known shifts
np.random.seed(42)
study1_ctrl = np.random.normal(loc=0.0, scale=1.0, size=200)
study1_trt  = np.random.normal(loc=0.4, scale=1.0, size=200)
np.random.seed(43)
study2_ctrl = np.random.normal(loc=0.0, scale=1.0, size=200)
study2_trt  = np.random.normal(loc=0.5, scale=1.2, size=200)

# Pin seed before each analysis
np.random.seed(42)
res1 = analyzer.analyze_study(study1_ctrl, study1_trt)
np.random.seed(42)
res2 = analyzer.analyze_study(study2_ctrl, study2_trt)

# Quantile differences (control vs treatment) — round generously since
# bootstrap SEs vary slightly, but point estimates should be stable.
# Effects are arrays per quantile.
print(json.dumps({
    "n_quantiles": len(analyzer.quantiles),
    "quantiles": [round(q, 4) for q in analyzer.quantiles],
    "study1_q25_eff_bc": round(float(res1["quantile_effects_bc"][0]), 3),
    "study1_q50_eff_bc": round(float(res1["quantile_effects_bc"][1]), 3),
    "study1_q75_eff_bc": round(float(res1["quantile_effects_bc"][2]), 3),
    "study1_slope":      round(float(res1["slope"]), 3),
    "study1_n_control":   int(res1["n_control"]),
    "study1_n_treatment": int(res1["n_treatment"]),
    "study1_mean_diff":   round(float(res1["mean_treatment"]) - float(res1["mean_control"]), 3),
    "study2_slope":       round(float(res2["slope"]), 3),
}))
''',
    },
    {
        "project_id_prefix": "asreview-5star",
        "project_path": r"C:\Projects\asreview_5star",
        "tolerance": 1e-4,
        "probe": '''
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
''',
    },
    {
        "project_id_prefix": "experimental-meta-analysis",
        "project_path": r"C:\Projects\experimental-meta-analysis",
        "tolerance": 1e-4,
        "probe": '''
import sys, json
import numpy as np
sys.path.insert(0, ".")
from core_framework import MetaAnalysisData, DerSimonianLaird, REML, PauleMandel

# Fixed 6-study meta-analysis input — small enough to be deterministic
# across scipy versions but representative of a typical pooled estimand.
data = MetaAnalysisData(
    effect_sizes=np.array([0.30, 0.45, 0.20, 0.55, 0.35, 0.40]),
    variances=np.array([0.04, 0.05, 0.03, 0.06, 0.04, 0.05]),
)

dl = DerSimonianLaird().estimate(data)
reml = REML().estimate(data)
pm = PauleMandel().estimate(data)

print(json.dumps({
    "n_studies": data.n_studies,
    "dl_pooled": round(float(dl.pooled_effect), 6),
    "dl_se": round(float(dl.pooled_se), 6),
    "dl_tau2": round(float(dl.tau2), 6),
    "dl_i2": round(float(dl.i2), 4),
    "dl_q": round(float(dl.q_stat), 6),
    "reml_pooled": round(float(reml.pooled_effect), 6),
    "reml_tau2": round(float(reml.tau2), 6),
    "pm_pooled": round(float(pm.pooled_effect), 6),
    "pm_tau2": round(float(pm.tau2), 6),
}))
''',
    },
    {
        "project_id_prefix": "transcendent-meta-analysis-lab",
        "project_path": r"C:\Projects\Transcendent-Meta-Analysis-Lab",
        "tolerance": 1e-4,
        "probe": '''
import sys, json
import numpy as np
sys.path.insert(0, ".")
from core.validation import safe_exp, safe_log, logsumexp_mean, ensure_positive_definite

# Pure math (deterministic)
e = safe_exp(2.0)
l = safe_log(7.5)
lse_mean = logsumexp_mean(np.array([1.0, 2.0, 3.0, 4.0, 5.0]))

# Matrix conditioning — fixed 2x2
M = np.array([[2.0, 0.99], [0.99, 1.0]])
M_pd = ensure_positive_definite(M, epsilon=1e-8)

# Edge cases
e_huge = safe_exp(1000.0)   # clipped to exp(700)
l_zero = safe_log(0.0)       # clipped to log(1e-300)

print(json.dumps({
    "exp_2": round(float(e), 6),
    "log_7_5": round(float(l), 6),
    "lse_mean_1_5": round(float(lse_mean), 6),
    "M_pd_diag0": round(float(M_pd[0, 0]), 6),
    "M_pd_diag1": round(float(M_pd[1, 1]), 6),
    "M_pd_off_diag": round(float(M_pd[0, 1]), 6),
    "exp_huge_clipped": round(float(e_huge), 0),
    "log_zero_clipped": round(float(l_zero), 4),
}))
''',
    },
    {
        "project_id_prefix": "moonshot-evidence-lab",
        "project_path": r"C:\Projects\moonshot-evidence-lab",
        "tolerance": 1e-4,
        "probe": '''
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
''',
    },
    {
        "project_id_prefix": "hfpef-registry-synth",
        "project_path": r"C:\Projects\hfpef_registry_synth",
        "tolerance": 1e-6,
        "probe": '''
import sys, json
sys.path.insert(0, "src")
from hfpef_registry_synth.utils import safe_float, safe_int, normalize_ws, parse_json_list, unique_preserve_order
from hfpef_registry_synth.parsing import is_hf_hosp_outcome, is_sae_outcome, parse_timeframe_months, endpoint_alignment_flags
from hfpef_registry_synth.mapping import classify_intervention, normalize_drug_label, is_hfpef_targeted

# Pure-function deterministic probes
sf = safe_float("3.14159")
si = safe_int("42")
# skip probing safe_float on bad input — it returns None which
# NumericalWitness treats as "missing in output", causing a false FAIL.
ws = normalize_ws("  hello   world  ")
jl = parse_json_list('["a", "b", "c"]')
upo = unique_preserve_order(["x", "y", "x", "z", "y", "w"])

# Domain functions
hf = is_hf_hosp_outcome("Heart failure hospitalization or cardiovascular death")
sae = is_sae_outcome("Serious adverse event including death")
tf_24 = parse_timeframe_months("24 months follow-up")
tf_2y = parse_timeframe_months("2 years")
ef = endpoint_alignment_flags([0.50, 0.55, 0.60, 0.45], tolerance=0.2)

cls = classify_intervention("empagliflozin", "drug")
ndl = normalize_drug_label("  Empagliflozin (Jardiance)  ")
hfpef = is_hfpef_targeted("preserved ejection fraction heart failure")

print(json.dumps({
    "safe_float_pi": round(sf, 5),
    "safe_int_42": si,
    "normalize_ws": ws,
    "parse_json_list_len": len(jl),
    "unique_order": upo,
    "is_hf_hosp": hf,
    "is_sae": sae,
    "tf_24mo": tf_24,
    "tf_2y": tf_2y,
    "endpoint_align_count": sum(ef),
    "classify_emp": cls.canonical_class if hasattr(cls, "canonical_class") else str(cls),
    "is_hfpef": hfpef,
}))
''',
    },
    {
        "project_id_prefix": "idea12",
        "project_path": r"C:\Projects\idea12",
        "tolerance": 1e-4,
        "probe": '''
import sys, json
import numpy as np
sys.path.insert(0, ".")
from netmetareg.core.data_structure import NMAData, Study
from netmetareg.models.frequentist_nma import FrequentistNMA

# Fixed 4-study A-B-C network (from tests/test_basic.py)
studies = [
    Study("S1", ["A", "B"], np.array([0.5]), np.array([0.1]),  np.array([100, 100])),
    Study("S2", ["B", "C"], np.array([0.3]), np.array([0.12]), np.array([100, 100])),
    Study("S3", ["A", "C"], np.array([0.8]), np.array([0.15]), np.array([100, 100])),
    Study("S4", ["A", "B"], np.array([0.6]), np.array([0.11]), np.array([100, 100])),
]
data = NMAData(studies, reference_treatment="A")

fe = FrequentistNMA(data, random_effects=False).fit()
re_results = FrequentistNMA(data, random_effects=True).fit()

# Treatment effect for B vs A (reference) under FE and RE
fe_B = fe.treatment_effects.set_index("treatment").loc["B", "effect"]
fe_C = fe.treatment_effects.set_index("treatment").loc["C", "effect"]
re_B = re_results.treatment_effects.set_index("treatment").loc["B", "effect"]
re_C = re_results.treatment_effects.set_index("treatment").loc["C", "effect"]
het = re_results.heterogeneity

print(json.dumps({
    "n_studies": data.n_studies,
    "n_treatments": data.n_treatments,
    "fe_effect_A": round(float(fe.treatment_effects.set_index("treatment").loc["A", "effect"]), 6),
    "fe_effect_B": round(float(fe_B), 6),
    "fe_effect_C": round(float(fe_C), 6),
    "re_effect_B": round(float(re_B), 6),
    "re_effect_C": round(float(re_C), 6),
    "tau_squared": round(float(het.get("tau_squared", 0.0)), 6),
    "I_squared":   round(float(het.get("I_squared",   0.0)), 4),
}))
''',
    },
    {
        "project_id_prefix": "lec-phase0-project",
        "project_path": r"C:\Projects\lec_phase0_project",
        "tolerance": 1e-4,
        "probe": '''
import sys, json
sys.path.insert(0, "src")
from lec.metaengine.statistics import calculate_meta_analysis_hksj

# Fixed 5-study deterministic input
studies = [
    {"estimate": 0.10, "se": 0.04},
    {"estimate": 0.15, "se": 0.05},
    {"estimate": 0.05, "se": 0.03},
    {"estimate": 0.20, "se": 0.06},
    {"estimate": 0.08, "se": 0.04},
]
r = calculate_meta_analysis_hksj(studies, use_hksj=True)
print(json.dumps({
    "pooled_estimate": round(r["pooled"]["estimate"], 6),
    "pooled_ci_low": round(r["pooled"]["ci_low"], 6),
    "pooled_ci_high": round(r["pooled"]["ci_high"], 6),
    "i2": round(r["heterogeneity"]["i2"], 4),
    "tau2": round(r["heterogeneity"]["tau2"], 6),
    "q": round(r["heterogeneity"]["q"], 4),
    "df": r["heterogeneity"]["df"],
    "pi_low": round(r["prediction_interval"]["pi_low"], 6),
    "pi_high": round(r["prediction_interval"]["pi_high"], 6),
    "hksj_ci_low": round(r["hksj_adjusted"]["ci_low"], 6),
    "hksj_ci_high": round(r["hksj_adjusted"]["ci_high"], 6),
    "n_studies": r["n_studies"],
}))
''',
    },
    {
        "project_id_prefix": "prognostic-meta",
        "project_path": r"C:\Users\user\prognostic-meta",
        "tolerance": 1e-4,
        "probe": '''
import sys, json
import numpy as np
sys.path.insert(0, ".")
from core.meta import inverse_variance_pooling, random_effects_pooling
from core.stats import smith_transform, inv_smith_transform, smith_se, oe_transform

y = np.array([0.10, 0.15, 0.05, 0.20, 0.08])
se = np.array([0.04, 0.05, 0.03, 0.06, 0.04])
mu_fe, se_fe, _w = inverse_variance_pooling(y, se)
mu_re, se_re, tau2, q, df = random_effects_pooling(y, se)
sm = smith_transform(0.85)
inv_sm = inv_smith_transform(sm)
sm_se = smith_se(0.85, 0.02)
oe_log = oe_transform(1.5)
print(json.dumps({
    "fe_mu": round(float(mu_fe), 6),
    "fe_se": round(float(se_fe), 6),
    "re_mu": round(float(mu_re), 6),
    "re_se": round(float(se_re), 6),
    "re_tau2": round(float(tau2), 6),
    "re_q": round(float(q), 6),
    "re_df": int(df),
    "smith_logit_0_85": round(float(sm), 6),
    "smith_inv_roundtrip": round(float(inv_sm), 6),
    "smith_se_at_0_85": round(float(sm_se), 6),
    "oe_log_1_5": round(float(oe_log), 6),
}))
''',
    },
    {
        # Added 2026-06-05 (fresh-discovery baseline; replaces decayed TODO).
        # math_score=6 (high) so the numerical witness fires; values are the
        # canonical Colditz BCG log-RR meta-analysis and are externally
        # validated against metafor by the project's own
        # ci/check_against_metafor.py (engine matches REML/DL within 2e-3).
        "project_id_prefix": "spec-collapse-atlas",
        "project_path": r"C:\Projects\spec-collapse-atlas",
        "tolerance": 1e-4,
        "probe": '''
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
''',
    },
    {
        # Added 2026-06-05. ma-workbench ships its OWN golden references
        # (golden/references/G*.json, PM/IV-validated and R-cross-checked). This
        # probes pool() on golden dataset G01 and reproduces the committed
        # reference exactly (pm_estimate=-0.19791392, tau2=0, qe=0.07720669).
        "project_id_prefix": "ma-workbench",
        "project_path": r"C:\Projects\ma-workbench",
        "tolerance": 1e-4,
        "probe": '''
import sys, json
sys.path.insert(0, ".")
from golden.generate_references import pool

ds = json.load(open("golden/datasets/G01-homogeneous-small.json", encoding="utf-8"))
r = pool(ds["bus_payload"]["studies"])
fe, pm = r["fe"], r["re_pm"]
print(json.dumps({
    "k": r["k"],
    "fe_estimate": round(fe["estimate"], 8),
    "fe_se": round(fe["se"], 8),
    "pm_estimate": round(pm["estimate"], 8),
    "pm_se": round(pm["se"], 8),
    "pm_tau2": round(pm["tau2"], 8),
    "pm_qe": round(pm["qe"], 8),
    "pm_i2_pct": round(pm["i2_pct"], 6),
}))
''',
    },
    {
        # Added 2026-06-05. The student starter's pairwise pooling tool
        # (Paule-Mandel tau2 + HKSJ-floor t CI). Fixed 5-study 2x2 input
        # (homogeneous, OR~0.6 => tau2=0, I2=0).
        "project_id_prefix": "e156-student-starter",
        "project_path": r"C:\Projects\e156-student-starter",
        "tolerance": 1e-4,
        "probe": '''
import sys, json
sys.path.insert(0, ".")
from tools.pool_pairwise import pool, Study

rows = [(20, 80, 30, 70), (15, 85, 25, 75), (25, 75, 35, 65),
        (10, 90, 18, 82), (22, 78, 28, 72)]
studies = [Study(label="S%d" % i, a=a, b=b, c=c, d=d)
           for i, (a, b, c, d) in enumerate(rows, 1)]
r = pool(studies)
print(json.dumps({
    "k": r["k"],
    "pooled_estimate": round(r["pooled_estimate"], 6),
    "pooled_or": round(r["pooled_or"], 6),
    "se": round(r["se"], 6),
    "ci_lower": round(r["ci_lower"], 6),
    "ci_upper": round(r["ci_upper"], 6),
    "q": round(r["q"], 6),
    "i2": round(r["i2"], 4),
    "tau2": round(r["tau2"], 6),
}))
''',
    },
    {
        # Added 2026-06-05. DL random-effects on canonical dat.bcg (log-RR):
        # reproduces metafor DL exactly (log_rr=-0.714117, tau2=0.308758, I2=92.1).
        "project_id_prefix": "hfpef-registry-calibration",
        "project_path": r"C:\Projects\hfpef-registry-calibration",
        "tolerance": 1e-4,
        "probe": '''
import sys, math, json
sys.path.insert(0, "src")
from hfpef_calibrate.meta import random_effects_pool

YI = [-0.889311, -1.585389, -1.348073, -1.441551, -0.217547, -0.786116,
      -1.620898, 0.011952, -0.469418, -1.371345, -0.339359, 0.445913, -0.017314]
VI = [0.325585, 0.194581, 0.415368, 0.02001, 0.05121, 0.006906, 0.223017,
      0.003962, 0.056434, 0.073025, 0.012412, 0.532506, 0.071405]
r = random_effects_pool(YI, [math.sqrt(v) for v in VI], "DL")
print(json.dumps({
    "k": r.k, "log_rr": round(r.log_rr, 6), "se": round(r.se, 6),
    "tau2": round(r.tau2, 6), "i2": round(r.i2, 4), "q": round(r.q, 6),
}))
''',
    },
    {
        # Added 2026-06-05. DL random-effects (HKSJ CI) on dat.bcg:
        # reproduces metafor DL (mu=-0.714117, tau2=0.308758).
        "project_id_prefix": "trial-truthfulness-atlas",
        "project_path": r"C:\Projects\trial-truthfulness-atlas",
        "tolerance": 1e-4,
        "probe": '''
import sys, json
sys.path.insert(0, "src")
from tta.meta import random_effects_pool

YI = [-0.889311, -1.585389, -1.348073, -1.441551, -0.217547, -0.786116,
      -1.620898, 0.011952, -0.469418, -1.371345, -0.339359, 0.445913, -0.017314]
VI = [0.325585, 0.194581, 0.415368, 0.02001, 0.05121, 0.006906, 0.223017,
      0.003962, 0.056434, 0.073025, 0.012412, 0.532506, 0.071405]
r = random_effects_pool(YI, VI)
print(json.dumps({
    "k": r.k, "mu": round(r.mu, 6), "tau2": round(r.tau2, 6),
    "ci_low": round(r.ci_low, 6), "ci_high": round(r.ci_high, 6),
}))
''',
    },
    {
        # Added 2026-06-05. Pure-Python DL pool on dat.bcg: reproduces metafor DL
        # exactly (estimate=-0.714117, tau2=0.308758, Q=152.23, I2=92.1).
        "project_id_prefix": "mission-critical",
        "project_path": r"C:\Projects\mission-critical",
        "tolerance": 1e-4,
        "probe": '''
import sys, json
import numpy as np
sys.path.insert(0, ".")
from mission_critical.diffmeta.engine import _python_pool

YI = np.array([-0.889311, -1.585389, -1.348073, -1.441551, -0.217547, -0.786116,
               -1.620898, 0.011952, -0.469418, -1.371345, -0.339359, 0.445913, -0.017314])
VI = np.array([0.325585, 0.194581, 0.415368, 0.02001, 0.05121, 0.006906, 0.223017,
               0.003962, 0.056434, 0.073025, 0.012412, 0.532506, 0.071405])
r = _python_pool(YI, VI, method="DL", measure="generic").to_dict()
print(json.dumps({
    "k": r["k"], "estimate": round(r["estimate"], 6), "se": round(r["se"], 6),
    "tau2": round(r["tau2"], 6), "i2": round(r["i2"], 4), "q": round(r["q"], 6),
}))
''',
    },
    {
        # Added 2026-06-05. DTA bivariate-DL pooling on the BNP-for-HF dataset
        # (the project's BNP_HF_STUDIES constant). The project ships an R/mada
        # validation (R_validation/validation_reference.json); this DL
        # approximation matches mada's bivariate GLMM within those stated
        # tolerances (Sens 0.865 vs 0.869, Spec 0.903 vs 0.902, I2_spec exact).
        "project_id_prefix": "metasprint-dta",
        "project_path": r"C:\Projects\metasprint-dta",
        "tolerance": 1e-4,
        "probe": '''
import sys, json
sys.path.insert(0, ".")
from dta_bivariate_reference import bivariate_dl_pool, BNP_HF_STUDIES

r = bivariate_dl_pool(BNP_HF_STUDIES)
print(json.dumps({
    "k": r["k"],
    "pooledSens": round(r["pooledSens"], 6),
    "pooledSpec": round(r["pooledSpec"], 6),
    "plr": round(r["plr"], 6),
    "nlr": round(r["nlr"], 6),
    "dor": round(r["dor"], 6),
    "I2_sens": round(r["I2_sens"], 4),
    "I2_spec": round(r["I2_spec"], 4),
    "tau2_spec": round(r["tau2_spec"], 6),
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
