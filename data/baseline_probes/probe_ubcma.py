import sys, json
sys.path.insert(0, r"C:\ubcma\src")
from ubcma.model import dersimonian_laird

yi = [0.5, 0.3, 0.8, 0.1, 0.6]
sei = [0.1, 0.2, 0.15, 0.25, 0.12]
result = dersimonian_laird(yi, sei)
print(json.dumps({
    "dl_mu": round(result["mu"], 6),
    "dl_tau": round(result["tau"], 6),
}))