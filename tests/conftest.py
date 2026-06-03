"""Shared pytest fixtures.

Hermetic environment (added 2026-06-03): Overmind's activation/wrap mechanism
exports ``OVERMIND_CONFIG_DIR`` / ``OVERMIND_DATA_DIR`` / ``OVERMIND_DB_PATH`` so a
wrapped Claude Code session points at the real workspace config and database. But
``AppConfig.from_directory`` gives those env vars precedence OVER its explicit
``config_dir`` / ``data_dir`` / ``db_path`` arguments (intentional for wrap). The
side effect: any unit test that constructs an isolated config via
``from_directory(config_dir=tmp_path/...)`` is silently overridden when the suite
runs inside an activated shell — it loads the REAL roots.yaml (scanning C:\\Projects
-> hundreds of projects instead of the one in the fixture) and the REAL runners.yaml
(so a test's synthetic ``codex_test`` runner does not exist and quota/adapter lookups
no-op). Four tests failed exactly this way (indexer x2, protocols adapter, runner
quota) only when OVERMIND_CONFIG_DIR was set in the environment.

This autouse fixture removes those vars before each test so tests are hermetic and
depend only on the paths they pass explicitly. Tests that deliberately exercise the
env-var precedence (e.g. test_config_paths) set the vars themselves via
``monkeypatch.setenv`` inside the test body, which runs after this fixture and is
restored afterwards — so they are unaffected.
"""
from __future__ import annotations

import pytest

_OVERMIND_PATH_ENV_VARS = (
    "OVERMIND_CONFIG_DIR",
    "OVERMIND_DATA_DIR",
    "OVERMIND_DB_PATH",
)


@pytest.fixture(autouse=True)
def _hermetic_overmind_env(monkeypatch):
    """Strip ambient OVERMIND_* path overrides so explicit test config wins."""
    for var in _OVERMIND_PATH_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    yield
