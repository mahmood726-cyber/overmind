"""Sequential chain runner for the Codex model comparison (feature branch).

Runs the remaining Codex arms + the significance micro-probe ONE AT A TIME so the
laptop SSH link is never asked to serve >3 concurrent codex execs (xhigh-at-high-
concurrency dropped links in the precision-fix run; sequential-medium is safe).
Stops loudly if any arm hits credit/quota exhaustion (returns 2)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ["gpt-5.5", "gpt-5.6-terra", "gpt-5.6-luna"]  # sol already run separately


def run(mod_args, label):
    print(f"\n########## {label} ##########", flush=True)
    p = subprocess.run([sys.executable, "-m"] + mod_args, cwd=str(ROOT))
    print(f"########## {label} exit={p.returncode} ##########", flush=True)
    return p.returncode


def main():
    # 1) main slice arms
    for m in MODELS:
        rc = run(["evals.codex_model_comparison", "--model", m], f"SLICE {m}")
        if rc == 2:
            print("STOP: credit exhaustion on main slice; not continuing.", flush=True)
            return 2
    # 2) significance micro-probe on ALL four models (sol included)
    for m in ["gpt-5.6-sol"] + MODELS:
        run(["evals.significance_probe", "--model", m], f"PROBE {m}")
    # 3) score everything
    run(["evals.codex_model_comparison", "--score"], "SCORE slices")
    run(["evals.significance_probe", "--score"], "SCORE probe")
    print("\nCHAIN COMPLETE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
