import sys, json, platform
platform._win32_ver = lambda *a, **k: ("10", "10.0.26100", "SP0", False)
platform._wmi_query = lambda *a, **k: "AMD64"
sys.path.insert(0, r"C:\MetaFrontierLab")
import pandas as pd
from metafrontier.core import FrontierMetaAnalyzer

df = pd.DataFrame({
    "yi": [0.5, 0.3, 0.8, 0.1, 0.6],
    "sei": [0.1, 0.2, 0.15, 0.25, 0.12],
})
analyzer = FrontierMetaAnalyzer()
result = analyzer.fit(df, effect_col="yi", se_col="sei")
print(json.dumps({
    "estimate": round(float(result.estimate), 6),
    "std_error": round(float(result.std_error), 6),
    "tau": round(float(result.tau), 6),
}))