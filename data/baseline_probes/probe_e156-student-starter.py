import sys, json
sys.path.insert(0, ".")
from tools.pool_pairwise import pool, Study

rows = [(20, 80, 30, 70), (15, 85, 25, 75), (25, 75, 35, 65),
        (10, 90, 18, 82), (22, 78, 28, 72)]
studies = [Study(label="S%d" % i, a=a, b=b, c=c, d=d)
           for i, (a, b, c, d) in enumerate(rows, 1)]
r = pool(studies)
print(json.dumps({
    "k": r["k"],
    "pooled_estimate": round(r["pooled_estimate"], 6),
    "pooled_or": round(r["pooled_or"], 6),
    "se": round(r["se"], 6),
    "ci_lower": round(r["ci_lower"], 6),
    "ci_upper": round(r["ci_upper"], 6),
    "q": round(r["q"], 6),
    "i2": round(r["i2"], 4),
    "tau2": round(r["tau2"], 6),
}))