from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from overmind.config import AppConfig, _source_checkout_data_dir, default_data_dir, default_db_path


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows path contract")


def test_default_paths_prefer_source_checkout_when_available(monkeypatch):
    package_root = Path(__file__).resolve().parents[2]
    monkeypatch.delenv("OVERMIND_DATA_DIR", raising=False)
    monkeypatch.delenv("OVERMIND_DB_PATH", raising=False)

    expected_data_dir = package_root / "data"
    assert _source_checkout_data_dir() == expected_data_dir
    assert default_data_dir() == expected_data_dir
    assert default_db_path() == expected_data_dir / "state" / "overmind.db"


def test_default_paths_fall_back_to_localappdata_without_source_checkout(monkeypatch):
    custom_localappdata = Path.home() / "codex_probe" / "overmind-localappdata"
    monkeypatch.delenv("OVERMIND_DATA_DIR", raising=False)
    monkeypatch.delenv("OVERMIND_DB_PATH", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(custom_localappdata))
    monkeypatch.setattr("overmind.config._source_checkout_data_dir", lambda: None)

    expected_data_dir = custom_localappdata / "Overmind"
    assert default_data_dir() == expected_data_dir
    assert default_db_path() == expected_data_dir / "state" / "overmind.db"


def test_appconfig_uses_repo_data_dir_by_default_in_source_checkout(monkeypatch):
    package_root = Path(__file__).resolve().parents[2]
    custom_localappdata = Path.home() / "codex_probe" / "overmind-config-defaults"
    shutil.rmtree(custom_localappdata, ignore_errors=True)
    monkeypatch.delenv("OVERMIND_DATA_DIR", raising=False)
    monkeypatch.delenv("OVERMIND_DB_PATH", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(custom_localappdata))

    config = AppConfig.from_directory(config_dir=package_root / "config")
    expected_data_dir = package_root / "data"
    try:
        assert config.data_dir == expected_data_dir
        assert config.db_path == expected_data_dir / "state" / "overmind.db"
        assert (expected_data_dir / "state").exists()
    finally:
        shutil.rmtree(custom_localappdata, ignore_errors=True)


def test_env_vars_override_explicit_args(monkeypatch, tmp_path):
    """Wrap-path precedence contract: OVERMIND_CONFIG_DIR/DATA_DIR/DB_PATH take
    precedence OVER explicit from_directory() args (overmind/config.py:138-146).

    The hermetic autouse fixture in conftest.py strips these vars before every test
    precisely BECAUSE they win — so no autouse-covered test can catch a regression in
    this precedence. This test re-sets all three (after the fixture's delenv) and
    asserts they still override deliberately-wrong explicit args, giving the wrap
    path a regression guard independent of the fixture. Pairs with the 2026-06-04
    review finding on the hermetic fixture masking the env-precedence path.
    """
    package_root = Path(__file__).resolve().parents[2]
    env_data = tmp_path / "env_data"
    env_db = tmp_path / "env_db" / "custom.db"
    monkeypatch.setenv("OVERMIND_CONFIG_DIR", str(package_root / "config"))
    monkeypatch.setenv("OVERMIND_DATA_DIR", str(env_data))
    monkeypatch.setenv("OVERMIND_DB_PATH", str(env_db))

    # Deliberately-wrong explicit args: the env vars must win over every one.
    config = AppConfig.from_directory(
        config_dir=tmp_path / "nonexistent_config",
        data_dir=tmp_path / "explicit_data",
        db_path=tmp_path / "explicit.db",
    )

    assert config.data_dir == env_data  # OVERMIND_DATA_DIR beat explicit data_dir
    assert config.db_path == env_db     # OVERMIND_DB_PATH beat explicit db_path
    # OVERMIND_CONFIG_DIR beat the (nonexistent) explicit config_dir: the real
    # runners.yaml loaded, so runners are present. Had the explicit empty dir won,
    # _load_yaml would have yielded {} and runners would be empty.
    assert config.runners, "env OVERMIND_CONFIG_DIR did not win: no runners loaded"
