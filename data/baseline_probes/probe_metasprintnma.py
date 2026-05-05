import sys, json, hashlib, re
from pathlib import Path

# HTML structural invariants — count tags + functions + content hash.
# Stable as long as the app's HTML doesn't change.
html_path = Path("metasprint-nma.html")
content = html_path.read_text(encoding="utf-8")
size_kb = round(len(content.encode("utf-8")) / 1024, 1)
n_lines = content.count("\n") + 1

# Count function definitions, script tags, key constructs
n_function = len(re.findall(r"function\s+\w+\s*\(", content))
n_arrow_func = len(re.findall(r"=>\s*\{", content))
n_script_tag = len(re.findall(r"<script", content))
n_div_tag = len(re.findall(r"<div", content))
n_svg_tag = len(re.findall(r"<svg", content))

content_hash_16 = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

print(json.dumps({
    "size_kb": size_kb,
    "n_lines": n_lines,
    "n_function_def": n_function,
    "n_arrow_func": n_arrow_func,
    "n_script_tag": n_script_tag,
    "n_div_tag": n_div_tag,
    "n_svg_tag": n_svg_tag,
    "content_hash_16": content_hash_16,
}))