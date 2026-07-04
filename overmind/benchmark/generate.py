"""Generate a held-out benchmark slice from the private gold corpus (§3).

Each 2x2 gold fixture (metafor-reproduced) yields four tasks with distinct,
DETERMINISTIC defects so the slice is balanced by construction:

  * clean            — true studies + true pooled RR + correct-direction claim (no defect)
  * impossible_cell  — one study corrupted so events > N (witness-detectable)
  * reproduction     — true studies + a perturbed claimed pooled RR (witness-detectable)
  * direction        — true studies + true RR + a conclusion in the WRONG direction
                       (reviewer-only; no deterministic witness)

Artifacts (what the reviewer sees) go to ``tasks.json``; the sealed answer keys go
to a SEPARATE ``keys.json`` the reviewer path never loads (blinding). All defect
choices are mechanical (no hand-picking), and the true pooled estimate is computed
by the engine (evidence/pooling) that reproduces metafor.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

from overmind.benchmark.tasks import (
    AnswerKey,
    Task,
    CLEAN,
    DIRECTION,
    IMPOSSIBLE_CELL,
    REPRODUCTION,
    save_keys,
    save_tasks,
)
from overmind.evidence.pooling import Study, pool

_GOLD_DIR = Path(__file__).resolve().parents[1] / "evidence" / "data" / "gold_reviews"

# Perturbation for the reproduction defect (mechanical, well outside tolerance).
_WRONG_ESTIMATE_FACTOR = 1.8
_REPRO_TOL = 0.05


def _true_ratio(fixture: dict) -> float | None:
    try:
        studies = [Study(**s) for s in fixture["studies"]]
        out = pool(studies, measure=fixture.get("measure", "RR"), method=fixture.get("method", "REML"))
        return out.get("estimate_ratio")
    except Exception:  # noqa: BLE001 — skip fixtures the engine can't pool cleanly
        return None


def _studies_table(studies: list[dict]) -> str:
    rows = ["  label | events(trt)/N(trt) | events(ctrl)/N(ctrl)"]
    for s in studies:
        rows.append(f"  {s.get('label','?')} | {s.get('ai')}/{s.get('n1')} | {s.get('ci')}/{s.get('n2')}")
    return "\n".join(rows)


def _slug(name: str, idx: int) -> str:
    base = "".join(c if c.isalnum() else "_" for c in name.lower())[:32].strip("_")
    return f"{base or 'fixture'}_{idx}"


def _load_2x2_fixtures() -> list[dict]:
    out = []
    for f in sorted(glob.glob(str(_GOLD_DIR / "*.json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        if d.get("kind") != "pooled":
            continue
        studies = d.get("studies", [])
        if studies and all(all(k in s for k in ("ai", "n1", "ci", "n2")) for s in studies):
            d["_file"] = Path(f).stem
            out.append(d)
    return out


def generate(max_fixtures: int | None = None) -> tuple[list[Task], list[AnswerKey]]:
    fixtures = _load_2x2_fixtures()
    tasks: list[Task] = []
    keys: list[AnswerKey] = []
    used = 0
    for idx, fx in enumerate(fixtures):
        true_ratio = _true_ratio(fx)
        if true_ratio is None:
            continue
        if max_fixtures is not None and used >= max_fixtures:
            break
        used += 1
        slug = _slug(fx.get("_file", fx.get("name", "fx")), idx)
        measure = fx.get("measure", "RR")
        method = fx.get("method", "REML")
        studies = [dict(s) for s in fx["studies"]]
        table = _studies_table(studies)
        direction_word = "reduces" if true_ratio < 1 else "increases"
        wrong_word = "increases" if true_ratio < 1 else "reduces"

        # 1) clean
        tasks.append(Task(
            f"{slug}__clean", CLEAN,
            f"Meta-analysis ({measure}, {method}). Studies:\n{table}\n"
            f"Claimed pooled {measure} = {true_ratio:.4f}. Conclusion: treatment {direction_word} the outcome.",
            data={"studies": studies, "measure": measure, "method": method,
                  "claimed_value": round(true_ratio, 4), "tolerance": _REPRO_TOL},
            source=fx.get("_file", ""),
        ))
        keys.append(AnswerKey(f"{slug}__clean", False, note="correct estimate + direction"))

        # 2) impossible cell (corrupt first study: events > N)
        bad = [dict(s) for s in studies]
        bad[0]["ai"] = bad[0]["n1"] + 5
        bad_table = _studies_table(bad)
        tasks.append(Task(
            f"{slug}__impossible", IMPOSSIBLE_CELL,
            f"Meta-analysis ({measure}, {method}). Studies:\n{bad_table}\n"
            f"Claimed pooled {measure} = {true_ratio:.4f}. Conclusion: treatment {direction_word} the outcome.",
            data={"studies": bad, "measure": measure, "method": method},
            source=fx.get("_file", ""),
        ))
        keys.append(AnswerKey(f"{slug}__impossible", True, "impossible_cell",
                              note=f"study 1 events {bad[0]['ai']} > N {bad[0]['n1']}"))

        # 3) reproduction (perturbed claimed estimate)
        wrong = round(true_ratio * _WRONG_ESTIMATE_FACTOR, 4)
        tasks.append(Task(
            f"{slug}__repro", REPRODUCTION,
            f"Meta-analysis ({measure}, {method}). Studies:\n{table}\n"
            f"Claimed pooled {measure} = {wrong}. Conclusion: treatment affects the outcome.",
            data={"studies": studies, "measure": measure, "method": method,
                  "claimed_value": wrong, "tolerance": _REPRO_TOL},
            source=fx.get("_file", ""),
        ))
        keys.append(AnswerKey(f"{slug}__repro", True, "wrong_pooled_estimate",
                              reference_value=round(true_ratio, 4), tolerance=_REPRO_TOL,
                              note=f"claimed {wrong} vs true {true_ratio:.4f}"))

        # 4) direction (true numbers, wrong conclusion direction)
        tasks.append(Task(
            f"{slug}__direction", DIRECTION,
            f"Meta-analysis ({measure}, {method}). Studies:\n{table}\n"
            f"Claimed pooled {measure} = {true_ratio:.4f}. Conclusion: treatment {wrong_word} the outcome.",
            data={"studies": studies, "measure": measure, "method": method,
                  "claimed_value": round(true_ratio, 4), "tolerance": _REPRO_TOL},
            source=fx.get("_file", ""),
        ))
        keys.append(AnswerKey(f"{slug}__direction", True, "wrong_direction",
                              note=f"true {measure}={true_ratio:.3f} ({direction_word}) but claims {wrong_word}"))

    return tasks, keys


def write_slice(out_dir: Path | str, *, max_fixtures: int | None = None) -> dict:
    out = Path(out_dir)
    tasks, keys = generate(max_fixtures=max_fixtures)
    save_tasks(out / "tasks.json", tasks)
    save_keys(out / "keys" / "keys.json", keys)   # sealed keys in a sibling dir
    return {"tasks": len(tasks), "keys": len(keys), "out_dir": str(out)}
