"""Bundle-level failure classification.

`overmind.parsing.failure_classifier` classifies what happened INSIDE an
agent session (loop detected, proof gap, idle, etc.). This module
classifies what happened TO a verification bundle (missing baseline,
import error, OneDrive reparse point, timeout, etc.). The distinction
matters because bundle failures bypass the agent entirely and need a
different remediation channel (fix the project contract, not change the
agent's strategy).

Classes are deliberately stable strings so they aggregate cleanly
across nights in the dream engine cluster analysis.
"""
from __future__ import annotations

import re

from overmind.verification.scope_lock import WitnessResult


# Canonical failure-class names. Keep stable — aggregated across nights.
FAILURE_CLASSES: dict[str, str] = {
    "missing_baseline": "numerical witness had no baseline file",
    "missing_module": "smoke module did not resolve to a file",
    "missing_path": "project root_path or working directory missing",
    "missing_executable": "test runner not found on PATH / not on disk",
    "missing_test_command": "project has no configured test command",
    "corrupt_baseline": "baseline file exists but is malformed",
    "import_error": "smoke witness failed on ImportError / ModuleNotFoundError",
    "timeout": "witness exceeded its timeout",
    "reparse_point": "Windows reparse point / OneDrive placeholder access failure",
    "permission_denied": "EACCES / WinError 5 during subprocess or file access",
    "agent_capacity": "LLM provider rejected with capacity error",
    "usage_limit": "LLM provider rejected with quota/usage-limit error",
    "policy_blocked": "PolicyGuard blocked the witness command before execution",
    "nondeterministic": "determinism witness observed differing output across runs",
    "unknown": "witness failed with no recognised pattern",
}


_IMPORT_ERROR_RE = re.compile(r"ModuleNotFoundError|ImportError: No module named", re.IGNORECASE)
_REPARSE_RE = re.compile(r"WinError 1920|cannot be accessed by the system", re.IGNORECASE)
_PERM_RE = re.compile(r"PermissionError|WinError 5\b|Access is denied|EACCES", re.IGNORECASE)
_CAPACITY_RE = re.compile(r"at capacity|too many (people|requests|connections)", re.IGNORECASE)
_USAGE_RE = re.compile(r"usage limit|quota exceeded|rate[- ]limit(ed)?", re.IGNORECASE)
_MISSING_EXEC_RE = re.compile(
    r"WinError 2\b|The system cannot find the file specified|"
    r"No such file or directory|command not found|\[Errno 2\]",
    re.IGNORECASE,
)
_MISSING_MODULE_RE = re.compile(
    r"modules? (imported OK|do not resolve|not importable)",
    re.IGNORECASE,
)


def classify_witness_failure(witness: WitnessResult) -> str:
    """Return the canonical failure class for a FAIL/SKIP witness result."""
    if witness.verdict == "PASS":
        return ""
    text = f"{witness.stdout}\n{witness.stderr}"

    if "Blocked:" in witness.stderr and "policy" in witness.stderr.lower():
        return "policy_blocked"
    if "Blocked: command prefix not allowlisted" in witness.stderr:
        return "missing_executable"

    if witness.verdict == "SKIP":
        if witness.witness_type == "numerical":
            return "missing_baseline"
        if witness.witness_type == "smoke":
            return "missing_module"
        return "unknown"

    if "Timed out" in witness.stderr or "timed out" in witness.stderr.lower():
        return "timeout"
    if _REPARSE_RE.search(text):
        return "reparse_point"
    if _PERM_RE.search(text):
        return "permission_denied"
    if _MISSING_EXEC_RE.search(text):
        return "missing_executable"
    if _IMPORT_ERROR_RE.search(text):
        return "import_error"
    if _CAPACITY_RE.search(text):
        return "agent_capacity"
    if _USAGE_RE.search(text):
        return "usage_limit"
    return "unknown"


def classify_bundle(witnesses: list[WitnessResult], preflight_class: str | None = None) -> str | None:
    """Pick the most informative failure class across bundle witnesses.

    Preflight failures always win (they bypass witness execution).
    Otherwise prefer specific classes over `unknown`, and prefer failing
    witnesses over skipped ones.
    """
    if preflight_class:
        return preflight_class
    if not witnesses:
        return None
    specific = [classify_witness_failure(w) for w in witnesses if w.verdict in {"FAIL", "SKIP"}]
    specific = [c for c in specific if c]
    if not specific:
        return None
    # Prefer non-"unknown" classes.
    for cls in specific:
        if cls != "unknown":
            return cls
    return "unknown"
