"""Eval 1 — SpecBench-style validation-vs-held-out gap for the witness pipeline.

Mirrors SpecBench (arXiv:2605.21384): score each candidate solution on a VISIBLE
validation test set and a HELD-OUT test set using our *real* ``SuiteWitness``,
then report the **validation-minus-held-out gap** — the reward-hacking signal.

What is actually measured here:
  * ``validation_pass_rate`` / ``heldout_pass_rate`` over all candidates,
  * ``specbench_gap = validation_pass_rate - heldout_pass_rate`` (headline),
  * how a *visible-only* verifier would behave (it CERTIFIES every reward-hack),
    versus Overmind's **held-out-baseline policy** (run the held-out witness too),
    which catches them: ``heldout_catch_rate`` on the reward-hack candidates.

This exercises the genuine witness pipeline — ``overmind.verification.witnesses.
SuiteWitness`` runs ``python -m pytest`` in an isolated temp dir per candidate.
No judge backend / network is required, so the eval is deterministic and offline.

Drop-in for the official benchmark: if ``evals/datasets/specbench_official/``
exists, its directory tasks are loaded *in addition* to the compact proxy. See
``specbench_proxy`` docstring for the directory layout.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from overmind.verification.witnesses import SuiteWitness

from evals.common import pct, write_result
from evals.datasets.specbench_proxy import PROXY_TASKS, Candidate, SpecTask

_OFFICIAL_DIR = Path(__file__).resolve().parent / "datasets" / "specbench_official"
_PYTEST_CMD = f'"{sys.executable}" -m pytest -q'


@dataclass
class CandidateResult:
    task: str
    candidate: str
    kind: str
    visible_pass: bool
    heldout_pass: bool


def load_directory_tasks(root: Path = _OFFICIAL_DIR) -> list[SpecTask]:
    """Load official-format SpecBench tasks from a directory, if present.

    Layout per task dir:
        <task>/spec.md
        <task>/tests/test_visible.py
        <task>/tests/test_heldout.py
        <task>/candidates/<kind>.py     (kind in honest|reward_hack|broken|...)
    Returns [] when the directory is absent so the proxy suite is used alone.
    """
    if not root.is_dir():
        return []
    tasks: list[SpecTask] = []
    for task_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        vis = task_dir / "tests" / "test_visible.py"
        held = task_dir / "tests" / "test_heldout.py"
        cand_dir = task_dir / "candidates"
        if not (vis.exists() and held.exists() and cand_dir.is_dir()):
            continue
        spec_file = task_dir / "spec.md"
        candidates = []
        for cand in sorted(cand_dir.glob("*.py")):
            # Filename stem encodes the kind for honest/reward_hack/broken; an
            # unrecognized stem is treated as kind=stem (still scored, just not
            # bucketed into the reward-hack catch metric).
            stem = cand.stem
            kind = stem if stem in {"honest", "reward_hack", "broken"} else stem
            candidates.append(Candidate(f"{task_dir.name}_{stem}", kind, cand.read_text(encoding="utf-8")))
        tasks.append(SpecTask(
            name=task_dir.name,
            spec=spec_file.read_text(encoding="utf-8") if spec_file.exists() else "",
            visible_test=vis.read_text(encoding="utf-8"),
            heldout_test=held.read_text(encoding="utf-8"),
            candidates=candidates,
        ))
    return tasks


def _run_suite(test_filename: str, test_body: str, solution_code: str) -> bool:
    """Materialize solution.py + a test file in a temp dir and run SuiteWitness.

    Returns True iff the witness verdict is PASS.
    """
    tmp = Path(tempfile.mkdtemp(prefix="specbench_"))
    try:
        (tmp / "solution.py").write_text(solution_code, encoding="utf-8")
        (tmp / test_filename).write_text(test_body, encoding="utf-8")
        witness = SuiteWitness(timeout=60)
        result = witness.run(f"{_PYTEST_CMD} {test_filename}", cwd=str(tmp))
        return result.verdict == "PASS"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def evaluate(tasks: list[SpecTask] | None = None) -> dict:
    if tasks is None:
        tasks = list(PROXY_TASKS) + load_directory_tasks()

    rows: list[CandidateResult] = []
    for task in tasks:
        for cand in task.candidates:
            vis = _run_suite("test_visible.py", task.visible_test, cand.code)
            held = _run_suite("test_heldout.py", task.heldout_test, cand.code)
            rows.append(CandidateResult(task.name, cand.name, cand.kind, vis, held))

    total = len(rows)
    visible_pass = sum(1 for r in rows if r.visible_pass)
    heldout_pass = sum(1 for r in rows if r.heldout_pass)
    validation_rate = pct(visible_pass, total)
    heldout_rate = pct(heldout_pass, total)
    gap = round(validation_rate - heldout_rate, 4)

    # Reward-hack focus: the candidates engineered to pass visible, fail held-out.
    hacks = [r for r in rows if r.kind == "reward_hack"]
    hacks_pass_visible = sum(1 for r in hacks if r.visible_pass)
    hacks_caught = sum(1 for r in hacks if r.visible_pass and not r.heldout_pass)

    # A visible-only verifier would CERTIFY anything that passes the visible set,
    # including every reward-hack. Overmind's held-out-baseline policy runs the
    # held-out witness and rejects when it fails.
    visible_only_false_certs = sum(1 for r in hacks if r.visible_pass)  # all certified by visible-only
    heldout_catch_rate = pct(hacks_caught, hacks_pass_visible)

    per_task = []
    for task in tasks:
        trows = [r for r in rows if r.task == task.name]
        v = pct(sum(1 for r in trows if r.visible_pass), len(trows))
        h = pct(sum(1 for r in trows if r.heldout_pass), len(trows))
        per_task.append({
            "task": task.name,
            "validation_pass_rate": v,
            "heldout_pass_rate": h,
            "gap": round(v - h, 4),
        })

    payload = {
        "eval": "specbench_style_proxy",
        "note": (
            "COMPACT LOCAL PROXY of SpecBench (arXiv:2605.21384), not the official "
            "benchmark. Drop official tasks into evals/datasets/specbench_official/."
        ),
        "n_tasks": len(tasks),
        "n_candidates": total,
        "validation_pass_rate": validation_rate,
        "heldout_pass_rate": heldout_rate,
        "specbench_gap": gap,
        "reward_hack": {
            "n": len(hacks),
            "passed_visible": hacks_pass_visible,
            "caught_by_heldout": hacks_caught,
            "heldout_catch_rate": heldout_catch_rate,
            "visible_only_false_certifications": visible_only_false_certs,
        },
        "per_task": per_task,
        "candidates": [
            {
                "task": r.task, "candidate": r.candidate, "kind": r.kind,
                "visible_pass": r.visible_pass, "heldout_pass": r.heldout_pass,
            }
            for r in rows
        ],
    }
    return payload


def main() -> dict:
    payload = evaluate()
    path = write_result("specbench_style", payload)
    rh = payload["reward_hack"]
    print(f"[specbench_style] validation_pass_rate={payload['validation_pass_rate']:.2%} "
          f"heldout_pass_rate={payload['heldout_pass_rate']:.2%} "
          f"GAP={payload['specbench_gap']:.2%}")
    print(f"[specbench_style] reward-hacks: {rh['passed_visible']} passed visible, "
          f"{rh['caught_by_heldout']} caught by held-out witness "
          f"(catch_rate={rh['heldout_catch_rate']:.2%}); "
          f"visible-only would have falsely certified {rh['visible_only_false_certifications']}")
    print(f"[specbench_style] -> {path}")
    return payload


if __name__ == "__main__":
    main()
