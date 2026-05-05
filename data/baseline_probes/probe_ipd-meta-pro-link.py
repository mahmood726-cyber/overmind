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