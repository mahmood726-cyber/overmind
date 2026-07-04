"""Benchmark task model + blinding + deterministic held-out split (§3).

A Task is what a reviewer SEES (an ``artifact`` string + structured ``data`` for
the objective witness). An AnswerKey is the SEALED ground truth — it lives in a
separate file the reviewer path never loads (blinding / "never read the test
split"). The held-out split is a deterministic hash of the task id, so dev vs
held-out is reproducible and not hand-picked.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

# Task kinds.
IMPOSSIBLE_CELL = "impossible_cell"   # a 2x2 table with events > N (witness-detectable)
REPRODUCTION = "reproduction"          # a claimed pooled estimate to check vs metafor (witness-detectable)
DIRECTION = "direction"                # a stated conclusion whose direction is wrong (reviewer-only)
CLEAN = "clean"                        # a correct artifact (must NOT be flagged)


@dataclass(slots=True)
class Task:
    id: str
    kind: str
    artifact: str                      # what the reviewer sees (NO answer key)
    data: dict = field(default_factory=dict)   # structured numbers for the objective witness
    source: str = ""                   # gold fixture it derives from

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "artifact": self.artifact,
                "data": self.data, "source": self.source}

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        return cls(id=d["id"], kind=d["kind"], artifact=d["artifact"],
                   data=dict(d.get("data", {})), source=d.get("source", ""))


@dataclass(slots=True)
class AnswerKey:
    id: str
    has_defect: bool
    defect_type: str = ""              # "" for clean
    reference_value: float | None = None   # for reproduction: the correct pooled estimate
    tolerance: float | None = None
    note: str = ""

    def to_dict(self) -> dict:
        return {"id": self.id, "has_defect": self.has_defect, "defect_type": self.defect_type,
                "reference_value": self.reference_value, "tolerance": self.tolerance, "note": self.note}

    @classmethod
    def from_dict(cls, d: dict) -> "AnswerKey":
        return cls(id=d["id"], has_defect=bool(d["has_defect"]), defect_type=d.get("defect_type", ""),
                   reference_value=d.get("reference_value"), tolerance=d.get("tolerance"),
                   note=d.get("note", ""))


def stable_bucket(task_id: str, *, salt: str = "") -> float:
    """Deterministic [0,1) bucket from the task id (sha256). No RNG state."""
    h = hashlib.sha256(f"{salt}:{task_id}".encode("utf-8")).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def held_out_ids(task_ids, *, holdout_fraction: float = 0.5, salt: str = "heldout-v1") -> set[str]:
    """Deterministic held-out id set (~holdout_fraction of tasks)."""
    return {tid for tid in task_ids if stable_bucket(tid, salt=salt) < holdout_fraction}


def load_tasks(path: Path | str) -> list[Task]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Task.from_dict(t) for t in data["tasks"]]


def save_tasks(path: Path | str, tasks: list[Task]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps({"tasks": [t.to_dict() for t in tasks]}, indent=1), encoding="utf-8")


def load_keys(path: Path | str) -> dict[str, AnswerKey]:
    """Load the SEALED answer keys. Only the SCORER may call this — never a
    reviewer/arm path (that would break blinding)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {k["id"]: AnswerKey.from_dict(k) for k in data["keys"]}


def save_keys(path: Path | str, keys: list[AnswerKey]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps({"keys": [k.to_dict() for k in keys]}, indent=1), encoding="utf-8")
