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