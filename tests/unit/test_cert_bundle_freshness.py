"""Tests for CertBundle.verify_freshness — replay-protection guard.

v6 benchmark gap #1 (2026-04-29). HMAC alone protects against forgery
but NOT replay; an attacker who obtained any old PASS bundle could
replay it as a fresh PASS. verify_freshness() pairs with
verify_signature() to require BOTH authenticity AND recency.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from overmind.verification.cert_bundle import CertBundle
from overmind.verification.scope_lock import ScopeLock, WitnessResult


def _scope_lock() -> ScopeLock:
    return ScopeLock(
        project_id="freshness-test",
        project_path="/tmp/freshness-test",
        risk_profile="low",
        witness_count=1,
        test_command="pytest",
        smoke_modules=(),
        baseline_path=None,
        expected_outcome="pass",
        source_hash="abcd1234",
        created_at="2026-01-01T00:00:00+00:00",
    )


def _bundle_at(timestamp: str) -> CertBundle:
    return CertBundle(
        project_id="freshness-test",
        scope_lock=_scope_lock(),
        witness_results=[WitnessResult(
            witness_type="test_suite", verdict="PASS", exit_code=0,
            stdout="", stderr="", elapsed=0.1,
        )],
        verdict="CERTIFIED",
        arbitration_reason="single witness PASS",
        timestamp=timestamp,
    )


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


# ── happy path ──────────────────────────────────────────────────────


def test_recent_bundle_is_fresh():
    now = datetime.now(timezone.utc)
    bundle = _bundle_at(_iso(now - timedelta(seconds=30)))
    assert bundle.verify_freshness(max_age_seconds=300)


def test_just_within_window_is_fresh():
    now = datetime.now(timezone.utc)
    bundle = _bundle_at(_iso(now - timedelta(seconds=290)))
    assert bundle.verify_freshness(max_age_seconds=300)


# ── replay protection — old bundle fails ────────────────────────────


def test_old_bundle_fails_freshness():
    """The core replay-protection assertion: an old PASS bundle must
    fail freshness even though its signature is still valid."""
    now = datetime.now(timezone.utc)
    old_bundle = _bundle_at(_iso(now - timedelta(days=180)))
    assert not old_bundle.verify_freshness(max_age_seconds=300)


def test_just_outside_window_fails():
    now = datetime.now(timezone.utc)
    bundle = _bundle_at(_iso(now - timedelta(seconds=400)))
    assert not bundle.verify_freshness(max_age_seconds=300)


def test_year_old_bundle_fails():
    now = datetime.now(timezone.utc)
    bundle = _bundle_at(_iso(now - timedelta(days=365)))
    assert not bundle.verify_freshness(max_age_seconds=24 * 3600)


# ── edge cases ──────────────────────────────────────────────────────


def test_future_timestamp_fails():
    """Future-dated bundle = clock skew or forgery. Reject.
    NOT 'fresh' just because it's not yet stale."""
    now = datetime.now(timezone.utc)
    future_bundle = _bundle_at(_iso(now + timedelta(hours=1)))
    assert not future_bundle.verify_freshness(max_age_seconds=86400)


def test_empty_timestamp_fails():
    bundle = _bundle_at("")
    assert not bundle.verify_freshness(max_age_seconds=86400)


def test_malformed_timestamp_fails():
    """Garbage timestamp → must NOT silently pass freshness."""
    bundle = _bundle_at("not a real timestamp")
    assert not bundle.verify_freshness(max_age_seconds=86400)


def test_z_suffix_timestamp_parses():
    """Bundles serialized with `Z` suffix (UTC) instead of `+00:00`
    must still parse — common JSON-serialization shape."""
    now = datetime.now(timezone.utc)
    ts = (now - timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    bundle = _bundle_at(ts)
    assert bundle.verify_freshness(max_age_seconds=300)


def test_naive_timestamp_treated_as_utc():
    """Pre-tzinfo bundles may have naive ISO-8601 stamps. Don't reject —
    treat as UTC so legacy bundles still validate freshness."""
    now = datetime.now(timezone.utc)
    naive_ts = (now - timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%S")
    bundle = _bundle_at(naive_ts)
    assert bundle.verify_freshness(max_age_seconds=300)


def test_signature_and_freshness_are_independent():
    """A bundle with valid signature but stale timestamp returns:
        verify_signature() = True
        verify_freshness() = False
    Callers that ONLY check signature would (wrongly) accept."""
    now = datetime.now(timezone.utc)
    old_bundle = _bundle_at(_iso(now - timedelta(days=30)))
    # Signature can't be verified here (no signer configured in test) —
    # what matters is that verify_freshness independently catches the
    # old timestamp regardless of signature state.
    assert not old_bundle.verify_freshness(max_age_seconds=86400)
