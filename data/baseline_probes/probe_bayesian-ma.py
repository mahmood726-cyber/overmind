import sys, json, hashlib, re
from pathlib import Path
html_path = Path("bayesian-ma.html")
content = html_path.read_text(encoding="utf-8")
print(json.dumps({
    "size_kb": round(len(content.encode("utf-8")) / 1024, 1),
    "n_lines": content.count("\n") + 1,
    "n_function_def": len(re.findall(r"function\s+\w+\s*\(", content)),
    "n_script_tag": len(re.findall(r"<script", content)),
    "n_div_tag": len(re.findall(r"<div", content)),
    "content_hash_16": hashlib.sha256(content.encode("utf-8")).hexdigest()[:16],
}))