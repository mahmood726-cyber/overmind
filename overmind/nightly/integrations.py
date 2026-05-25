"""Sentinel / bypass aggregation helpers extracted from nightly_verify.py.

Wraps the integration-package collectors with the soft-fail behavior the
nightly relies on. Behavior is unchanged.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from overmind.integrations.sentinel_aggregator import collect as _collect_sentinel
from overmind.integrations.bypass_log_aggregator import collect as _collect_bypass


def collect_sentinel_findings() -> dict:
    """Thin wrapper around overmind.integrations.sentinel_aggregator.collect.

    Kept as a module-level name so the nightly_verify tests and report
    can refer to it without importing the integration module directly.
    """
    return _collect_sentinel()


def _run_portfolio_sentinel_scan() -> dict:
    """Invoke `sentinel scan --portfolio` and summarise verdict counts.

    Portfolio-scope rules (registry_drift, path_not_exist, memory_paths_resolve,
    livingmeta_drift, agent_config_version_drift) run against the central
    project index rather than any one repo, so this scan surfaces drift that
    pre-push hooks never see because they fire per-repo-per-push.

    Fails soft: returns an error dict if the sentinel CLI isn't available,
    the scan crashes, or JSON parsing fails. Nightly verify must not crash
    here.

    Default project-index: C:/ProjectIndex (the canonical portfolio
    registry); override via OVERMIND_PROJECT_INDEX env var for tests.
    """
    project_index = os.environ.get("OVERMIND_PROJECT_INDEX", "C:/ProjectIndex")
    if not Path(project_index).is_dir():
        return {"error": f"project-index not found: {project_index}"}
    try:
        # OVERMIND_PROJECT_INDEX is an internal-tooling env var sourced from the
        # operator's shell, not from any network surface. List-arg form,
        # shell=False — no shell injection vector.
        # Timeout was 180s; bumped to 600s 2026-05-08 after the portfolio
        # added 4 rules + tightened excludes (which require deeper file
        # walks). The full --portfolio scan now legitimately exceeds 180s
        # on a fresh registry walk; 600s is comfortably above current ~250s
        # observed wall-clock.
        result = subprocess.run(
            [sys.executable, "-m", "sentinel", "scan",  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-tainted-env-args.dangerous-subprocess-use-tainted-env-args
             "--portfolio", "--project-index", project_index, "--json"],
            capture_output=True, text=True, timeout=600,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return {"error": f"{type(e).__name__}: {e}"}

    if result.returncode >= 2:
        return {
            "error": f"sentinel scan exit {result.returncode}",
            "stderr": (result.stderr or "")[:500],
        }

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        return {"error": f"json decode: {e}", "stdout": result.stdout[:500]}

    verdicts = data.get("verdicts", [])
    by_severity = {"BLOCK": 0, "WARN": 0, "INFO": 0}
    by_rule: dict = {}
    for v in verdicts:
        sev = v.get("severity") or "UNKNOWN"
        by_severity[sev] = by_severity.get(sev, 0) + 1
        rid = v.get("rule_id") or "UNKNOWN"
        by_rule[rid] = by_rule.get(rid, 0) + 1

    return {
        "total_block": by_severity.get("BLOCK", 0),
        "total_warn": by_severity.get("WARN", 0),
        "total_info": by_severity.get("INFO", 0),
        "by_rule": by_rule,
        "project_index": project_index,
    }


def collect_bypass_findings(window_days: int = 7) -> dict:
    """Thin wrapper around bypass_log_aggregator.collect.

    Surfaces repeat Sentinel bypassers in the nightly report so enforcement
    can't go silently dark. Fails soft — a missing log is normal (nobody
    has bypassed yet).
    """
    return _collect_bypass(window_days=window_days)
