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