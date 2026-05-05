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