import sys, json, csv, statistics
from pathlib import Path

# Read the canonical IAI output and emit class counts + summary stats.
# All deterministic: the CSV is checked into the repo per the manuscript.
ia_path = Path("analysis/output/information_adequacy/information_adequacy_FINAL.csv")
with ia_path.open(encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

iai_classes = {}
for r in rows:
    c = r["IAI_final_class"]
    iai_classes[c] = iai_classes.get(c, 0) + 1

iai_vals = [float(r["IAI_final"]) for r in rows if r["IAI_final"]]

print(json.dumps({
    "n_ma": len(rows),
    "adequate_count":   iai_classes.get("Adequate", 0),
    "marginal_count":   iai_classes.get("Marginal", 0),
    "inadequate_count": iai_classes.get("Inadequate", 0),
    "critical_count":   iai_classes.get("Critical", 0),
    "iai_mean":   round(statistics.mean(iai_vals), 4),
    "iai_median": round(statistics.median(iai_vals), 4),
    "iai_min":    round(min(iai_vals), 4),
    "iai_max":    round(max(iai_vals), 4),
}))