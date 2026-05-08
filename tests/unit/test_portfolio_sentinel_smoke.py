"""Smoke test for _run_portfolio_sentinel_scan.

Guards against regression of the NameError observed in
nightly_2026-05-06.json:138-140 ("live scan crashed: NameError: name 'os'
is not defined"). Root cause was an older Sentinel version; resolved by
Sentinel commits e6c3163, 5fb4599, 61fbc20 (skip-marker refactor +
baselines exclusion). This test pins the contract so a future Sentinel
regression surfaces in CI rather than at 03:00 in production.

The wrapper in nightly_verify is `try/except` so a real Sentinel crash
turns into an `error` field — this test asserts the field shape both for
the happy path (Sentinel returns counts) and the soft-fail path
(Sentinel missing or returning malformed JSON).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import nightly_verify  # noqa: E402


def test_run_portfolio_sentinel_scan_returns_dict():
    """Function must return a dict; never raise."""
    result = nightly_verify._run_portfolio_sentinel_scan()
    assert isinstance(result, dict)


def test_run_portfolio_sentinel_scan_dict_shape():
    """Either the count keys are present (success) or 'error' is (soft-fail)."""
    result = nightly_verify._run_portfolio_sentinel_scan()
    success_keys = {"total_block", "total_warn", "total_info", "by_rule", "project_index"}
    has_success = success_keys.issubset(result.keys())
    has_error = "error" in result
    assert has_success or has_error, (
        f"unexpected shape: keys={list(result.keys())}; "
        f"expected either {success_keys} or {{error}}"
    )


def test_run_portfolio_sentinel_scan_handles_missing_index(monkeypatch):
    """When OVERMIND_PROJECT_INDEX points nowhere, fail soft with an error dict."""
    monkeypatch.setenv("OVERMIND_PROJECT_INDEX", "C:/this/does/not/exist")
    result = nightly_verify._run_portfolio_sentinel_scan()
    assert "error" in result
    assert "project-index not found" in result["error"]


def test_os_module_visible_in_function_scope():
    """Direct guard against the 2026-05-06 NameError. The function uses
    os.environ.get() at module scope — this asserts os is importable from
    the same scope nightly_verify uses.
    """
    import inspect
    src = inspect.getsource(nightly_verify._run_portfolio_sentinel_scan)
    # The function must reference os.environ (otherwise this test loses
    # its anchor) AND the module must have os available.
    assert "os.environ" in src
    assert hasattr(nightly_verify, "os")
