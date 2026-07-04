"""Tests for the vendor auth preflight (reliability item 3). Uses injected
backends — no CLI, no quota. Asserts a REAL exec smoke (not login status) and
that a 401/unavailable seat is reported degraded, never falsely live."""
from __future__ import annotations

from overmind.reliability.auth_preflight import (
    degraded_seats,
    live_vendors,
    preflight_agy,
    preflight_all,
    preflight_codex,
    summarize,
)
from overmind.verification.judge_backends import JUDGE_ERROR


class _Backend:
    def __init__(self, response, available=True):
        self._response = response
        self._available = available
    def available(self):
        return self._available
    def query(self, prompt):
        return self._response


def test_codex_both_seats_live():
    backends = {"mahmood": _Backend("READY"), "noreen": _Backend("READY")}
    probes = preflight_codex(backends=backends)
    assert all(p.alive for p in probes)
    assert {p.seat for p in probes} == {"mahmood", "noreen"}
    assert all(p.vendor == "codex" for p in probes)


def test_codex_401_seat_degraded_not_live():
    backends = {
        "mahmood": _Backend("READY"),
        "noreen": _Backend(f"{JUDGE_ERROR} exit 401: refresh token revoked"),
    }
    probes = preflight_codex(backends=backends)
    by_seat = {p.seat: p for p in probes}
    assert by_seat["mahmood"].alive is True
    assert by_seat["noreen"].alive is False
    assert "401" in by_seat["noreen"].detail


def test_agy_live():
    p = preflight_agy(backend=_Backend("42"))
    assert p.vendor == "agy" and p.alive is True


def test_agy_error_degraded():
    p = preflight_agy(backend=_Backend(f"{JUDGE_ERROR} agy driver crashed"))
    assert p.alive is False


def test_agy_unavailable():
    p = preflight_agy(backend=_Backend("x", available=False))
    assert p.alive is False
    assert "unavailable" in p.detail


def test_preflight_all_composes():
    codex = {"mahmood": _Backend("READY"), "noreen": _Backend(f"{JUDGE_ERROR} 401")}
    probes = preflight_all(codex_backends=codex, agy_backend=_Backend("42"))
    assert live_vendors(probes) == ["agy", "codex"]  # codex has 1 live seat
    dead = degraded_seats(probes)
    assert [p.seat for p in dead] == ["noreen"]


def test_summarize_string():
    codex = {"mahmood": _Backend("READY"), "noreen": _Backend("READY")}
    probes = preflight_all(codex_backends=codex, agy_backend=_Backend("42"))
    s = summarize(probes)
    assert "live=" in s and "degraded=none" in s


def test_all_degraded_no_live_vendors():
    codex = {"mahmood": _Backend(f"{JUDGE_ERROR} 401"), "noreen": _Backend(f"{JUDGE_ERROR} 401")}
    probes = preflight_all(codex_backends=codex, agy_backend=_Backend(f"{JUDGE_ERROR} down"))
    assert live_vendors(probes) == []
    assert len(degraded_seats(probes)) == 3
