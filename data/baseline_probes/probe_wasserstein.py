import sys, json
sys.path.insert(0, r"C:\Projects\wasserstein")
from improved_hr_estimation import estimate_hr_from_curves

times1 = [0, 6, 12, 18, 24]
surv1 = [1.0, 0.85, 0.70, 0.55, 0.40]
times2 = [0, 6, 12, 18, 24]
surv2 = [1.0, 0.80, 0.60, 0.45, 0.30]
result = estimate_hr_from_curves(times1, surv1, times2, surv2, n1=100, n2=100)
print(json.dumps({
    "hr": round(result["hr"], 6),
}))