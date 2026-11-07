"""B2/B3: gate tooling must not hardcode local paths or run at import."""
from __future__ import annotations

import importlib
import sys

import pytest

from overmind.gates import resolver as resolver_mod
from overmind.gates import sink as sink_mod


def test_measure_arm_gate_import_is_side_effect_free(monkeypatch):
    # B2: importing must not connect to a hardcoded duckdb or need duckdb at all.
    monkeypatch.delenv("OVERMIND_AACT_DUCKDB", raising=False)
    monkeypatch.setitem(sys.modules, "duckdb", None)  # import duckdb -> ImportError
    sys.modules.pop("overmind.gates.measure_arm_gate", None)
    mod = importlib.import_module("overmind.gates.measure_arm_gate")
    assert callable(mod.main)


def test_measure_arm_gate_main_requires_env_var(monkeypatch, capsys):
    monkeypatch.delenv("OVERMIND_AACT_DUCKDB", raising=False)
    mod = importlib.import_module("overmind.gates.measure_arm_gate")
    assert mod.main() == 2
    assert "OVERMIND_AACT_DUCKDB" in capsys.readouterr().err


def test_resolver_has_no_hardcoded_aact_default(monkeypatch):
    monkeypatch.delenv("OVERMIND_AACT_DUCKDB", raising=False)
    # even if every path "exists", no baked-in location may be returned
    monkeypatch.setattr(resolver_mod.os.path, "exists", lambda p: True)
    assert resolver_mod._default_aact_path() is None


def test_resolver_env_override_still_works(monkeypatch, tmp_path):
    f = tmp_path / "aact.duckdb"
    f.write_bytes(b"")
    monkeypatch.setenv("OVERMIND_AACT_DUCKDB", str(f))
    assert resolver_mod._default_aact_path() == str(f)


def test_sink_roots_require_explicit_config(monkeypatch):
    monkeypatch.delenv("OVERMIND_DELIVERABLE_ROOTS", raising=False)
    with pytest.raises(RuntimeError, match="OVERMIND_DELIVERABLE_ROOTS"):
        sink_mod.default_deliverable_roots()


def test_sink_roots_from_env(monkeypatch, tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    monkeypatch.setenv("OVERMIND_DELIVERABLE_ROOTS", str(a) + __import__("os").pathsep + str(tmp_path / "missing"))
    assert sink_mod.default_deliverable_roots() == [str(a)]
