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