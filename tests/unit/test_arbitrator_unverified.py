"""Arbitrator behavior for missing-baseline numerical SKIP (UNVERIFIED verdict).

Per 2026-04-15 bug: `cert_bundle.Arbitrator.arbitrate` used to downgrade
tier-3 projects with a missing numerical baseline to verdict="PASS".
That counted as a positive verdict in the nightly report (line 444:
`success = verdict in ("CERTIFIED", "PASS")`), which violated the
testing.md rule: "A numerical witness SKIP because the baseline is
missing is not a release pass and does not justify promoting the
project status."

Fix: arbitrator now returns verdict="UNVERIFIED" for this case —
distinct from PASS/CERTIFIED (positive) and SKIP (all witnesses skipped).
"""
from __future__ import annotations
from overmind.verification.cert_bundle import Arbitrator
from overmind.verification.scope_lock import WitnessResult


def _w(witness_type: str, verdict: str) -> WitnessResult:
    return WitnessResult(
        witness_type=witness_type, verdict=verdict, exit_code=0 if verdict == "PASS" else None,
        stdout="", stderr="", elapsed=0.1,
    )


def test_tier3_all_three_pass_is_certified():
    """Baseline behavior: when numerical witness ran AND passed, verdict=CERTIFIED."""
    arb = Arbitrator()
    verdict, reason = arb.arbitrate([
        _w("test_suite", "PASS"),
        _w("smoke", "PASS"),
        _w("numerical", "PASS"),
    ])
    assert verdict == "CERTIFIED"
    assert "3/3" in reason


def test_tier3_numerical_skip_missing_baseline_is_unverified():
    """THE REGRESSION GUARD: tier-3 with numerical SKIP → UNVERIFIED, not PASS.

    Prior behavior returned 'PASS' which nightly_verify counted as success.
    That let projects ship CERTIFIED-adjacent badges without ever running
    the numerical regression check they required.
    """
    arb = Arbitrator()
    verdict, reason = arb.arbitrate([
        _w("test_suite", "PASS"),
        _w("smoke", "PASS"),
        _w("numerical", "SKIP"),
    ])
    assert verdict == "UNVERIFIED", (
        f"expected UNVERIFIED for tier-3 with missing numerical baseline, got {verdict!r}"
    )
    assert "baseline missing" in reason.lower()
    assert "NOT a release pass" in reason


def test_tier2_two_pass_stays_certified():
    """Tier-2 (no numerical witness expected): 2/2 PASS → CERTIFIED."""
    arb = Arbitrator()
    verdict, reason = arb.arbitrate([
        _w("test_suite", "PASS"),
        _w("smoke", "PASS"),
    ])
    assert verdict == "CERTIFIED"
    assert "2/2" in reason


def test_tier1_single_pass_is_pass_not_unverified():
    """Single-witness projects return PASS (not UNVERIFIED) — they never
    had a numerical witness to miss in the first place."""
    arb = Arbitrator()
    verdict, reason = arb.arbitrate([
        _w("test_suite", "PASS"),
    ])
    assert verdict == "PASS"
    assert "Single witness" in reason


def test_all_witnesses_skipped_is_skip_not_unverified():
    """Distinct from UNVERIFIED: when ALL witnesses skip, verdict=SKIP.
    UNVERIFIED specifically means 'some witnesses passed, numerical missed'."""
    arb = Arbitrator()
    verdict, reason = arb.arbitrate([
        _w("test_suite", "SKIP"),
        _w("smoke", "SKIP"),
        _w("numerical", "SKIP"),
    ])
    assert verdict == "SKIP"
    assert "All witnesses skipped" in reason


def test_tier3_numerical_skip_with_test_fail_stays_fail():
    """If the test witness FAILS, the whole verdict is FAIL regardless of
    the numerical SKIP. UNVERIFIED is only for the 'all non-skipped passed'
    case with a missing baseline."""
    arb = Arbitrator()
    verdict, reason = arb.arbitrate([
        _w("test_suite", "FAIL"),
        _w("smoke", "PASS"),
        _w("numerical", "SKIP"),
    ])
    # FAIL + PASS with numerical SKIP → non_skip = {FAIL, PASS} → REJECT (disagreement)
    assert verdict == "REJECT"
