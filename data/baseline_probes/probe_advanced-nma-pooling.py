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