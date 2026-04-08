import sys, json, platform
platform._win32_ver = lambda *a, **k: ("10", "10.0.26100", "SP0", False)
platform._wmi_query = lambda *a, **k: "AMD64"
sys.path.insert(0, r"C:\MetaAudit")
import numpy as np
from metaaudit.recompute import compute_log_or, compute_smd

lor = compute_log_or(np.array([30]), np.array([100]), np.array([15]), np.array([100]))
smd = compute_smd(np.array([10.0]), np.array([2.0]), np.array([50]), np.array([8.0]), np.array([2.5]), np.array([50]))
print(json.dumps({
    "logOR": round(float(lor[0][0]), 6),
    "logOR_se": round(float(lor[1][0]), 6),
    "smd": round(float(smd[0][0]), 6),
    "smd_se": round(float(smd[1][0]), 6),
}))