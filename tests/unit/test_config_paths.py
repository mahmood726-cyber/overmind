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
