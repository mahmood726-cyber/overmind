import sys, json
sys.path.insert(0, r"C:\Models\AfricaForecast")
from engine.validate import compute_rmse, compute_mae, compute_coverage

actual = [1.0, 2.0, 3.0, 4.0, 5.0]
predicted = [1.1, 1.9, 3.2, 3.8, 5.1]
lo = [0.8, 1.6, 2.8, 3.5, 4.7]
hi = [1.4, 2.3, 3.5, 4.2, 5.4]
rmse = compute_rmse(actual, predicted)
mae = compute_mae(actual, predicted)
cov = compute_coverage(actual, lo, hi)
print(json.dumps({
    "rmse": round(rmse, 6),
    "mae": round(mae, 6),
    "coverage": round(cov, 6),
}))