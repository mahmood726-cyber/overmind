"""Shared helpers for the eval harness: deterministic seeding + results I/O."""
from __future__ import annotations

import json
import os
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Fixed seed for any stochastic step. The evals are designed to be deterministic
# from fixed fixtures; this is belt-and-suspenders so a future randomized step
# stays reproducible.
SEED = 1234

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def seed_everything(seed: int = SEED) -> None:
    random.seed(seed)
    os.environ.setdefault("PYTHONHASHSEED", str(seed))


def _generated_at() -> str:
    # Metadata only — never used in a scored field, so results scores stay
    # byte-reproducible across runs even though this timestamp changes.
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_result(name: str, payload: dict[str, Any]) -> Path:
    """Write a result JSON to evals/results/<name>.json and return the path.

    ``payload`` should carry the scored numbers; we add a ``generated_at``
    metadata stamp under ``_meta`` so the scores themselves remain reproducible.
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = dict(payload)
    meta = dict(out.get("_meta", {}))
    meta["generated_at"] = _generated_at()
    out["_meta"] = meta
    path = RESULTS_DIR / f"{name}.json"
    path.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    return path


def pct(numerator: float, denominator: float) -> float:
    """Safe ratio rounded to 4 dp (avoids div-by-zero per house rules)."""
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)
