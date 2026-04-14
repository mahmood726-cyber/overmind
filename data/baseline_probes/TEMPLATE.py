"""Baseline probe template — copy to probe_<project_slug>.py and fill in.

A baseline probe is a deterministic Python script that runs a target
project's numerical code on a *fixed* input and prints a JSON object of
stable, small-scale output values. The TruthCert NumericalWitness runs
the probe, parses the JSON, and compares values against
`data/baselines/<project_id>.json` with tolerance (default 1e-6).

Contract with NumericalWitness:
- stdout MUST be valid JSON (one object, no banner text before or after)
- values SHOULD round to 6 decimal places for stability across platforms
- inputs MUST be fixed literals (no randomness, no clock, no filesystem
  reads of potentially-changing data) — otherwise the witness will flap
- stderr output is ignored for PASS/FAIL but shown in the bundle when
  the probe errors

How to fill this in:
1. Copy this file to `data/baseline_probes/probe_<slug>.py` (see TODO.md
   for slug suggestions per project).
2. Replace the `sys.path.insert` line with the real project root.
3. Replace the import line with the project's entrypoint function(s).
4. Feed fixed literal inputs to the entrypoint(s). Small realistic
   values are best — enough to exercise the math without pulling in
   data files.
5. Round and emit values you want to track. Typical signals:
     meta-analysis:         theta, tau2, i2, CI bounds
     network MA:            SUCRA ranks, edge effects
     diagnostic accuracy:   sensitivity, specificity, DOR, AUC
     survival:              HR, log-rank p, RMST
     bayesian:              posterior mean/sd, r_hat, ESS (pinned seed)
6. Run it manually once:
     python data\\baseline_probes\\probe_<slug>.py
   The output JSON becomes the first baseline.
7. Save the accepted baseline as:
     data\\baselines\\<project_id>.json
   in the format:
     {"command": "<absolute-python-path> <probe-path>", "values": {...}, "tolerance": 1e-6}

See `probe_metaaudit.py` (logOR/SMD) or `probe_fragilityatlas.py`
(DL/REML-HKSJ pooling) for worked examples.
"""
import json
import platform
import sys

# Windows / Python 3.13 WMI deadlock guard — harmless on other platforms.
platform._win32_ver = lambda *a, **k: ("10", "10.0.26100", "SP0", False)
platform._wmi_query = lambda *a, **k: "AMD64"

# TODO: replace with the project root as a raw-string Windows path.
sys.path.insert(0, r"C:\Path\To\Project")

# TODO: import the entrypoint function(s) from the project.
# from <project_package>.<module> import <function>

# TODO: define fixed inputs — literals only, no randomness, no files.
# Small representative values are usually enough to pin the numerics.

# TODO: call the entrypoint(s) and capture whatever scalars are stable.
# result = <function>(<inputs>)

# TODO: emit a single JSON object. Round floats for cross-platform
# stability. Do not print anything else before or after this line.
print(json.dumps({
    # "metric_name": round(float(result.value), 6),
}))
