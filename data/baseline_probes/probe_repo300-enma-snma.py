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