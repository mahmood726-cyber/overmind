"""Shared filesystem constants for the nightly verifier.

Single source of truth so both `scripts/nightly_verify.py` and the
extracted `overmind.nightly.*` submodules resolve to the same paths.
"""
from __future__ import annotations

from pathlib import Path

# `parents[2]` because this file is overmind/overmind/nightly/paths.py;
# overmind repo root is two levels up from the inner package.
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DB_PATH = DATA_DIR / "state" / "overmind.db"
REPORT_DIR = DATA_DIR / "nightly_reports"
