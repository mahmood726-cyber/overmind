"""Machine-aware config (P3-a): ${ENV}/~ expansion + roots.local.yaml merge."""
from __future__ import annotations

from pathlib import Path

from overmind.config import AppConfig


def test_env_expansion_and_local_merge(tmp_path, monkeypatch):
    for var in ("OVERMIND_CONFIG_DIR", "OVERMIND_DATA_DIR", "OVERMIND_DB_PATH"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OM_TEST_ROOT", str(tmp_path))

    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "roots.yaml").write_text(
        'scan_roots:\n  - "${OM_TEST_ROOT}/shared"\n  - "~"\n', encoding="utf-8")
    (cfg / "roots.local.yaml").write_text(
        'scan_roots:\n  - "${OM_TEST_ROOT}/local"\n', encoding="utf-8")

    data = tmp_path / "data"
    app = AppConfig.from_directory(config_dir=cfg, data_dir=data, db_path=data / "x.db")
    roots = {str(p) for p in app.roots.scan_roots}

    assert str(tmp_path / "shared") in roots          # ${ENV} expanded
    assert str(tmp_path / "local") in roots           # merged from roots.local.yaml
    assert str(Path("~").expanduser()) in roots       # ~ expanded


def test_dedup_case_insensitive(tmp_path, monkeypatch):
    for var in ("OVERMIND_CONFIG_DIR", "OVERMIND_DATA_DIR", "OVERMIND_DB_PATH"):
        monkeypatch.delenv(var, raising=False)
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "roots.yaml").write_text(
        'scan_roots:\n  - "C:/Projects"\nscan_rules: {}\n', encoding="utf-8")
    (cfg / "roots.local.yaml").write_text(
        'scan_roots:\n  - "c:/projects"\n', encoding="utf-8")  # same path, diff case
    data = tmp_path / "data"
    app = AppConfig.from_directory(config_dir=cfg, data_dir=data, db_path=data / "x.db")
    assert len(app.roots.scan_roots) == 1
