"""Generate a held-out benchmark slice from the private gold corpus (§3).

Each 2x2 gold fixture (metafor-reproduced) yields TEN tasks — a clean one plus nine
defects spanning witness-detectable and reviewer-only classes — so the slice is
large and balanced by construction:

  WITNESS-DETECTABLE (a deterministic check on the data fires):
    * impossible_cell  — one study corrupted so events > N
    * reproduction     — a perturbed claimed pooled estimate
    * ci_invalid       — a transposed confidence interval (lo > hi)

  REVIEWER-ONLY (data passes EVERY deterministic check; defect is in the narrative
  only — these mirror REAL errors we hit and are what the panel must catch):
    * direction            — conclusion direction contradicts the data
    * wrong_measure_label  — ratio data described as a continuous (MD) outcome   [MD->"RR" mislabel]
    * method_mismatch      — naive pool claimed despite strong funnel asymmetry  [Copas naive-pool]
    * comparator_swap      — narrative swaps treatment/control arms              [pubHR comparator mismatch]
    * missing_reference    — claims historical borrowing but no reference/null arm [RM-BRIDGE missing null]
    * subgroup_mismatch    — analysis label doesn't match the outcome described  [analysis/coding mismatch]

Artifacts (what the reviewer sees) -> ``tasks.json``; sealed answer keys ->
``keys/keys.json`` (a gitignored dir the reviewer path never loads). Defect choices
are mechanical (no hand-picking); the true pooled estimate + CI come from the engine
(evidence/pooling) that reproduces metafor. For every reviewer-only task the
``data`` is left valid (true value, valid CI, valid counts) so the deterministic
battery cannot fire — only a reasoning reviewer can catch it.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

from overmind.benchmark.tasks import (
    AnswerKey,
    Task,
    CLEAN,
    CI_INVALID,
    COMPARATOR_SWAP,
    DIRECTION,
    IMPOSSIBLE_CELL,
    METHOD_MISMATCH,
    MISSING_REFERENCE,
    OVERSTATED_SIGNIFICANCE,
    REPRODUCTION,
    SUBGROUP_MISMATCH,
    WRONG_MEASURE_LABEL,
    save_keys,
    save_tasks,
)
from overmind.evidence.pooling import Study, pool

_GOLD_DIR = Path(__file__).resolve().parents[1] / "evidence" / "data" / "gold_reviews"

_WRONG_ESTIMATE_FACTOR = 1.8
_REPRO_TOL = 0.05


def _true_stats(fixture: dict):
    try:
        studies = [Study(**s) for s in fixture["studies"]]
        out = pool(studies, measure=fixture.get("measure", "RR"), method=fixture.get("method", "REML"))
        ratio = out.get("estimate_ratio")
        ci = out.get("ci_ratio")
        if ratio is None:
            return None, None
        return ratio, (ci if ci else [ratio * 0.8, ratio * 1.25])
    except Exception:  # noqa: BLE001
        return None, None


def _studies_table(studies: list[dict]) -> str:
    rows = ["  label | events(trt)/N(trt) | events(ctrl)/N(ctrl)"]
    for s in studies:
        rows.append(f"  {s.get('label','?')} | {s.get('ai')}/{s.get('n1')} | {s.get('ci')}/{s.get('n2')}")
    return "\n".join(rows)


def _slug(name: str, idx: int) -> str:
    base = "".join(c if c.isalnum() else "_" for c in name.lower())[:32].strip("_")
    return f"{base or 'fixture'}_{idx}"


def _artifact(measure, method, table, claimed, ci, conclusion, *, extra="") -> str:
    ci_s = f"[{ci[0]:.4f}, {ci[1]:.4f}]"
    body = (f"Meta-analysis ({measure}, {method} random-effects). Studies:\n{table}\n"
            f"Claimed pooled {measure} = {claimed:.4f}, 95% CI {ci_s}.")
    if extra:
        body += f"\n{extra}"
    body += f"\nConclusion: {conclusion}"
    return body


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
        true_ratio, true_ci = _true_stats(fx)
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
        dir_word = "reduces" if true_ratio < 1 else "increases"
        wrong_dir = "increases" if true_ratio < 1 else "reduces"
        # valid data block reused by clean + all reviewer-only tasks (witnesses must pass)
        valid_data = {"studies": studies, "measure": measure, "method": method,
                      "claimed_value": round(true_ratio, 4), "claimed_ci": [round(true_ci[0], 4), round(true_ci[1], 4)],
                      "tolerance": _REPRO_TOL}

        def _add(suffix, kind, artifact, data, key: AnswerKey):
            tasks.append(Task(f"{slug}__{suffix}", kind, artifact, data=data, source=fx.get("_file", "")))
            keys.append(key)

        # --- clean ---
        _add("clean", CLEAN,
             _artifact(measure, method, table, true_ratio, true_ci,
                       f"treatment {dir_word} the outcome."),
             dict(valid_data),
             AnswerKey(f"{slug}__clean", False, note="correct estimate, CI, direction, measure, method"))

        # --- witness-detectable ---
        bad = [dict(s) for s in studies]; bad[0]["ai"] = bad[0]["n1"] + 5
        _add("impossible", IMPOSSIBLE_CELL,
             _artifact(measure, method, _studies_table(bad), true_ratio, true_ci,
                       f"treatment {dir_word} the outcome."),
             {"studies": bad, "measure": measure, "method": method},
             AnswerKey(f"{slug}__impossible", True, "impossible_cell",
                       note=f"study 1 events {bad[0]['ai']} > N {bad[0]['n1']}"))

        wrong = round(true_ratio * _WRONG_ESTIMATE_FACTOR, 4)
        _add("repro", REPRODUCTION,
             _artifact(measure, method, table, wrong, true_ci,
                       "treatment affects the outcome."),
             {"studies": studies, "measure": measure, "method": method,
              "claimed_value": wrong, "tolerance": _REPRO_TOL},
             AnswerKey(f"{slug}__repro", True, "wrong_pooled_estimate",
                       reference_value=round(true_ratio, 4), tolerance=_REPRO_TOL,
                       note=f"claimed {wrong} vs true {true_ratio:.4f}"))

        _add("ci_invalid", CI_INVALID,
             _artifact(measure, method, table, true_ratio, [true_ci[1], true_ci[0]],
                       f"treatment {dir_word} the outcome."),
             {"studies": studies, "measure": measure, "method": method,
              "claimed_value": round(true_ratio, 4), "claimed_ci": [round(true_ci[1], 4), round(true_ci[0], 4)]},
             AnswerKey(f"{slug}__ci_invalid", True, "transposed_ci",
                       note=f"CI lower {true_ci[1]:.3f} > upper {true_ci[0]:.3f}"))

        # --- reviewer-only (data valid; defect in narrative) ---
        _add("direction", DIRECTION,
             _artifact(measure, method, table, true_ratio, true_ci,
                       f"treatment {wrong_dir} the outcome."),
             dict(valid_data),
             AnswerKey(f"{slug}__direction", True, "wrong_direction",
                       note=f"true {measure}={true_ratio:.3f} ({dir_word}) but claims {wrong_dir}"))

        _add("measure_label", WRONG_MEASURE_LABEL,
             _artifact(measure, method, table, true_ratio, true_ci,
                       f"treatment {dir_word} the outcome.",
                       extra="Outcome: mean change in continuous score (reported as a mean difference)."),
             dict(valid_data),
             AnswerKey(f"{slug}__measure_label", True, "wrong_measure_label",
                       note=f"data are event/total counts pooled as {measure}, but described as a continuous mean difference"))

        _add("method_mismatch", METHOD_MISMATCH,
             _artifact(measure, method, table, true_ratio, true_ci,
                       f"treatment {dir_word} the outcome.",
                       extra="Note: strong small-study/funnel asymmetry present; reported as a naive pooled "
                             "estimate with no selection-model (Copas) adjustment."),
             dict(valid_data),
             AnswerKey(f"{slug}__method_mismatch", True, "method_mismatch",
                       note="naive pool reported despite stated funnel asymmetry requiring selection-model adjustment"))

        _add("comparator_swap", COMPARATOR_SWAP,
             _artifact(measure, method, table, true_ratio, true_ci,
                       "the control group received the active treatment and the treatment group received placebo; "
                       f"on that basis the intervention {wrong_dir} the outcome."),
             dict(valid_data),
             AnswerKey(f"{slug}__comparator_swap", True, "comparator_swap",
                       note="narrative swaps which arm is treatment vs control, inverting the comparator"))

        _add("missing_reference", MISSING_REFERENCE,
             _artifact(measure, method, table, true_ratio, true_ci,
                       f"treatment {dir_word} the outcome.",
                       extra="Method: estimate borrows strength from a historical control arm — but no "
                             "reference/null arm or borrowing prior is shown in the data above."),
             dict(valid_data),
             AnswerKey(f"{slug}__missing_reference", True, "missing_reference",
                       note="claims historical borrowing/adjustment but the required reference/null arm is absent"))

        _add("subgroup_mismatch", SUBGROUP_MISMATCH,
             _artifact(measure, method, table, true_ratio, true_ci,
                       f"in the pre-specified subgroup, treatment {dir_word} the outcome.",
                       extra="Analysis label: 'subgroup restricted to paediatric patients' — but the studies "
                             "above are the full adult+paediatric set (no subgroup restriction applied)."),
             dict(valid_data),
             AnswerKey(f"{slug}__subgroup_mismatch", True, "subgroup_mismatch",
                       note="analysis label claims a subgroup restriction that the data do not reflect"))

        # --- overstated significance (cross-vendor review P0-3, 2026-07-11) ---
        # A conclusion that CLAIMS a statistically significant / conclusive effect
        # while the reported 95% CI SPANS the null (includes 1.0) is a defect — the
        # data are valid (point estimate + CI correct, direction matches), so no
        # deterministic witness fires and the calibrated "a CI crossing 1.0 is not a
        # defect" rule alone would wave it through. Only generated when the true CI
        # actually spans 1.0 (otherwise the claim would be true, not a defect).
        if true_ci[0] < 1.0 < true_ci[1]:
            _add("overstated_significance", OVERSTATED_SIGNIFICANCE,
                 _artifact(measure, method, table, true_ratio, true_ci,
                           f"treatment SIGNIFICANTLY {dir_word} the outcome — a statistically "
                           f"significant, conclusive effect was demonstrated."),
                 dict(valid_data),
                 AnswerKey(f"{slug}__overstated_significance", True, "overstated_significance",
                           note=f"conclusion claims a SIGNIFICANT/conclusive effect but 95% CI "
                                f"[{true_ci[0]:.4f}, {true_ci[1]:.4f}] includes 1.0 (non-significant)"))

    return tasks, keys


def write_slice(out_dir: Path | str, *, max_fixtures: int | None = None) -> dict:
    out = Path(out_dir)
    tasks, keys = generate(max_fixtures=max_fixtures)
    save_tasks(out / "tasks.json", tasks)
    save_keys(out / "keys" / "keys.json", keys)
    return {"tasks": len(tasks), "keys": len(keys), "out_dir": str(out)}
