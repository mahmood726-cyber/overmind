"""Tests for the cross-vendor check stage (T11 / T-CV / WORLD_CLASS_SPEC D1)
plus the additive CodexBackend reasoning-effort knob.

All backends are injected — no CLI spawned, no quota burned. The stage is
ADVISORY: it must record presence + decorrelation and never claim a pass it
didn't earn (AUTH_DEGRADED when no live different-family checker).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from overmind.verification.cross_vendor_check import (
    CANARY_ARTIFACT,
    CrossVendorChecker,
    check_mode,
    is_found_nothing_pass,
    smoke_probe_codex_seats,
)
from overmind.verification.judge_backends import JUDGE_ERROR, CodexBackend


def _capturing_runner(captured: dict, response: str):
    def run(argv, stdin_text, env_overrides, timeout):
        captured["argv"] = argv
        captured["stdin"] = stdin_text
        captured["env"] = env_overrides
        return response
    return run


# --- CodexBackend effort knob (additive; None == byte-identical) ----------------

def test_codex_effort_none_is_byte_identical(tmp_path, monkeypatch):
    monkeypatch.setenv("OVERMIND_CODEX_HOME_MAHMOOD", str(tmp_path))
    cap: dict = {}
    CodexBackend(seat="mahmood", runner=_capturing_runner(cap, "ok")).query("p")
    assert "--config" not in cap["argv"]
    assert "model_reasoning_effort" not in " ".join(cap["argv"])
    # sanity: still the standard argv
    assert cap["argv"][-1] == "-"


def test_codex_effort_appends_config(tmp_path, monkeypatch):
    monkeypatch.setenv("OVERMIND_CODEX_HOME_MAHMOOD", str(tmp_path))
    cap: dict = {}
    CodexBackend(seat="mahmood", effort="xhigh", runner=_capturing_runner(cap, "ok")).query("p")
    assert "--config" in cap["argv"]
    assert "model_reasoning_effort=xhigh" in cap["argv"]
    # config override must come before the trailing stdin marker
    assert cap["argv"].index("--config") < cap["argv"].index("-")


def test_codex_effort_low_probe(tmp_path, monkeypatch):
    monkeypatch.setenv("OVERMIND_CODEX_HOME_MAHMOOD", str(tmp_path))
    cap: dict = {}
    CodexBackend(seat="mahmood", effort="low", runner=_capturing_runner(cap, "ok")).query("p")
    assert "model_reasoning_effort=low" in cap["argv"]


# --- fake backends for the checker stage ----------------------------------------

class _FakeBackend:
    def __init__(self, response: str, available: bool = True):
        self._response = response
        self._available = available
        self.calls: list[str] = []

    def available(self) -> bool:
        return self._available

    def query(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self._response


# --- check_mode -----------------------------------------------------------------

def test_check_mode_default_off(monkeypatch):
    monkeypatch.delenv("OVERMIND_CROSS_VENDOR_CHECK", raising=False)
    assert check_mode() == "off"


def test_check_mode_shadow(monkeypatch):
    monkeypatch.setenv("OVERMIND_CROSS_VENDOR_CHECK", "shadow")
    assert check_mode() == "shadow"


# --- stage behaviour ------------------------------------------------------------

def test_disabled_by_default_no_call(monkeypatch):
    monkeypatch.delenv("OVERMIND_CROSS_VENDOR_CHECK", raising=False)
    codex = _FakeBackend("VERDICT: PASS")
    checker = CrossVendorChecker(backends={"codex": codex})
    result = checker.check("some code", writer_engine="claude")
    assert result.present is False
    assert result.reason == "disabled"
    assert codex.calls == []  # no call made when off


def test_decorrelated_check_runs_and_parses(monkeypatch):
    monkeypatch.setenv("OVERMIND_CROSS_VENDOR_CHECK", "shadow")
    codex = _FakeBackend(
        "- [P0] events exceed N in 2x2 table (dash.js:12)\nVERDICT: BLOCK"
    )
    checker = CrossVendorChecker(checker_engines=("codex",), backends={"codex": codex})
    result = checker.check("cE=524 cN=39", writer_engine="claude")
    assert result.present is True
    assert result.decorrelated is True            # openai != anthropic
    assert result.writer_family == "anthropic"
    assert result.checker_family == "openai"
    assert result.verdict == "BLOCK"
    assert len(result.findings) == 1
    assert result.findings[0].severity == "P0"
    assert len(codex.calls) == 1


def test_same_family_checker_is_skipped(monkeypatch):
    # writer is codex (openai); the only checker offered is codex (openai) -> no
    # decorrelated checker available -> AUTH_DEGRADED, not a fake pass.
    monkeypatch.setenv("OVERMIND_CROSS_VENDOR_CHECK", "shadow")
    codex = _FakeBackend("VERDICT: PASS")
    checker = CrossVendorChecker(checker_engines=("codex",), backends={"codex": codex})
    result = checker.check("code", writer_engine="codex")
    assert result.present is False
    assert "AUTH_DEGRADED" in result.reason
    assert codex.calls == []


def test_auth_degraded_when_no_backend_available(monkeypatch):
    monkeypatch.setenv("OVERMIND_CROSS_VENDOR_CHECK", "shadow")
    codex = _FakeBackend("VERDICT: PASS", available=False)
    checker = CrossVendorChecker(checker_engines=("codex",), backends={"codex": codex})
    result = checker.check("code", writer_engine="claude")
    assert result.present is False
    assert "AUTH_DEGRADED" in result.reason


def test_falls_through_to_available_family(monkeypatch):
    monkeypatch.setenv("OVERMIND_CROSS_VENDOR_CHECK", "shadow")
    # codex down, agy up -> agy (google) is different family from claude
    codex = _FakeBackend("x", available=False)
    agy = _FakeBackend("VERDICT: PASS")
    checker = CrossVendorChecker(
        checker_engines=("codex", "agy"), backends={"codex": codex, "agy": agy}
    )
    result = checker.check("code", writer_engine="claude")
    assert result.present is True
    assert result.checker_engine == "agy"
    assert result.checker_family == "google"


def test_checker_error_is_not_a_pass(monkeypatch):
    monkeypatch.setenv("OVERMIND_CROSS_VENDOR_CHECK", "shadow")
    codex = _FakeBackend(f"{JUDGE_ERROR} exit 401: unauthorized")
    checker = CrossVendorChecker(checker_engines=("codex",), backends={"codex": codex})
    result = checker.check("code", writer_engine="claude")
    assert result.present is False
    assert "checker_error" in result.reason


def test_advisory_never_blocks_returns_result(monkeypatch):
    # even a BLOCK verdict is returned as advisory data, not raised/enforced
    monkeypatch.setenv("OVERMIND_CROSS_VENDOR_CHECK", "shadow")
    codex = _FakeBackend("- [P0] bug (f.js:1)\nVERDICT: BLOCK")
    checker = CrossVendorChecker(checker_engines=("codex",), backends={"codex": codex})
    result = checker.check("code", writer_engine="claude")
    # result is data; caller decides. to_dict carries the T-CV gate field.
    d = result.to_dict()
    assert d["cross_vendor_check_present"] is True
    assert d["decorrelated"] is True
    assert d["num_findings"] == 1


def test_prompt_includes_artifact(monkeypatch):
    monkeypatch.setenv("OVERMIND_CROSS_VENDOR_CHECK", "shadow")
    codex = _FakeBackend("VERDICT: PASS")
    checker = CrossVendorChecker(checker_engines=("codex",), backends={"codex": codex})
    checker.check("SENTINEL_ARTIFACT_XYZ", writer_engine="claude")
    assert "SENTINEL_ARTIFACT_XYZ" in codex.calls[0]


# --- Codex-seat smoke probe (T5 attestation) ------------------------------------

def test_smoke_probe_both_seats_alive():
    backends = {"mahmood": _FakeBackend("READY"), "noreen": _FakeBackend("READY")}
    probes = smoke_probe_codex_seats(backends=backends)
    assert [p.seat for p in probes] == ["mahmood", "noreen"]
    assert all(p.alive for p in probes)


def test_smoke_probe_flags_401_seat():
    backends = {
        "mahmood": _FakeBackend("READY"),
        "noreen": _FakeBackend(f"{JUDGE_ERROR} exit 401: unauthorized"),
    }
    probes = smoke_probe_codex_seats(backends=backends)
    by_seat = {p.seat: p for p in probes}
    assert by_seat["mahmood"].alive is True
    assert by_seat["noreen"].alive is False
    assert "401" in by_seat["noreen"].detail


def test_smoke_probe_flags_unavailable_seat():
    backends = {"mahmood": _FakeBackend("x", available=False), "noreen": _FakeBackend("READY")}
    probes = smoke_probe_codex_seats(backends=backends)
    by_seat = {p.seat: p for p in probes}
    assert by_seat["mahmood"].alive is False
    assert "unavailable" in by_seat["mahmood"].detail


# --- cE>cN canary (the RapidMeta P0-denominator-logic family) -------------------

def test_canary_flags_impossible_cell(monkeypatch):
    monkeypatch.setenv("OVERMIND_CROSS_VENDOR_CHECK", "shadow")
    # a real bug-finder flags the impossible cell
    codex = _FakeBackend(
        "- [P0] events cE=524 exceed N cN=39 — impossible 2x2 cell (rapidmeta)\nVERDICT: BLOCK"
    )
    checker = CrossVendorChecker(checker_engines=("codex",), backends={"codex": codex})
    result = checker.check(CANARY_ARTIFACT, writer_engine="claude")
    assert result.present is True
    assert result.findings, "canary: checker must flag the planted cE>cN defect"
    assert is_found_nothing_pass(result) is False


def test_found_nothing_pass_on_canary_is_failure(monkeypatch):
    monkeypatch.setenv("OVERMIND_CROSS_VENDOR_CHECK", "shadow")
    # a checker that PASSes the known-buggy canary with no findings = canary FAILURE
    codex = _FakeBackend("Looks fine to me.\nVERDICT: PASS")
    checker = CrossVendorChecker(checker_engines=("codex",), backends={"codex": codex})
    result = checker.check(CANARY_ARTIFACT, writer_engine="claude")
    assert is_found_nothing_pass(result) is True  # canary catches the empty pass


def test_canary_artifact_contains_impossible_cell():
    assert "cE=524" in CANARY_ARTIFACT and "cN=39" in CANARY_ARTIFACT
