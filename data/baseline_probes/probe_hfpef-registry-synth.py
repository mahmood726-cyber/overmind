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