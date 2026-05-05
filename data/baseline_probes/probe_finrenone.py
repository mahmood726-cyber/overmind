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