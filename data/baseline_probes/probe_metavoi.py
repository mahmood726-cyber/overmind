import sys, json, platform
platform._win32_ver = lambda *a, **k: ("10", "10.0.26100", "SP0", False)
platform._wmi_query = lambda *a, **k: "AMD64"
sys.path.insert(0, r"C:\Models\MetaVoI")
import numpy as np
from metavoi.evpi import compute_evpi

draws = np.array([0.1, 0.2, 0.3, 0.15, 0.25, 0.35, 0.05, 0.4, 0.22, 0.18])
evpi_02 = compute_evpi(draws, mcid=0.2)
evpi_01 = compute_evpi(draws, mcid=0.1)
print(json.dumps({
    "evpi_mcid02": round(float(evpi_02), 6),
    "evpi_mcid01": round(float(evpi_01), 6),
    "draws_mean": round(float(np.mean(draws)), 6),
    "draws_std": round(float(np.std(draws)), 6),
}))