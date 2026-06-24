"""Eval 6 — CoT golden-set no-regression gate (audit A3).

The precondition the roadmap sets for flipping ``OVERMIND_JUDGE_COT`` ON by
default: *the CoT + rubric prompt must not regress the judge on the golden set*.
This eval is that gate, made reproducible.

What it checks (offline, deterministic):
  1. **Parse-invariance / no-regression** — every golden verdict, run through a
     judge with CoT **OFF** and with CoT **ON**, yields the *same* effective
     verdict. (The CoT change is a PROMPT change; the parser + degenerate guard
     are untouched, so a well-formed verdict must classify identically.)
  2. **Guard still holds with CoT on** — degenerate false-PASS rate stays 0.
  3. **Structural validity** — the CoT prompt actually contains the
     RELEVANCE/ACCURACY/EVIDENCE/LOGIC rubric AND the intact six-line output
     contract the parser depends on.

> **Honest limit (truth-first):** this proves CoT is SAFE to enable (no parse
> regression, guard intact, contract preserved). It does **NOT** measure CoT's
> reasoning-quality *improvement* — that needs a live model (the StubBackend
> ignores the prompt). The expected quality gain is from the literature
> (arXiv:2604.23178: +11.2pp for Claude Sonnet 4 with CoT+rubric), NOT a number
> we measured here. We flip the default because it is safe + literature-backed,
> and we say plainly that the gain is unquantified until a live golden-set run.
"""
from __future__ import annotations

from overmind.verification.llm_judge import (
    JUDGE_PROMPT_TEMPLATE_COT,
    LLMJudge,
    StubBackend,
)
from overmind.storage.models import ProjectRecord, TaskRecord, VerificationResult

from evals.common import pct, write_result
from evals.judge_masterkey import _DEGENERATE, _GENUINE, _dummy_inputs, _effective_pass


def evaluate() -> dict:
    task, project, result = _dummy_inputs()

    golden = _GENUINE + _DEGENERATE
    agree = 0
    cot_on_genuine_correct = 0
    cot_off_genuine_correct = 0
    cot_on_degenerate_false_pass = 0
    rows = []

    for case in golden:
        off = LLMJudge(backend=StubBackend(response=case.response), use_cot=False)
        on = LLMJudge(backend=StubBackend(response=case.response), use_cot=True)
        v_off = off.judge(task, project, result)
        v_on = on.judge(task, project, result)
        p_off = _effective_pass(v_off)
        p_on = _effective_pass(v_on)
        same = p_off == p_on
        agree += int(same)
        if case.bucket == "genuine":
            cot_off_genuine_correct += int(p_off == case.expect_pass)
            cot_on_genuine_correct += int(p_on == case.expect_pass)
        if case.bucket == "degenerate":
            cot_on_degenerate_false_pass += int(p_on)
        rows.append({"name": case.name, "bucket": case.bucket,
                     "cot_off_pass": p_off, "cot_on_pass": p_on, "agree": same})

    n_genuine = sum(1 for c in golden if c.bucket == "genuine")
    n_degen = sum(1 for c in golden if c.bucket == "degenerate")

    # Structural validity of the CoT prompt.
    sample_prompt = LLMJudge(use_cot=True)._build_prompt(
        task, project, result, ["(transcript)"]
    )
    rubric_terms = ["RELEVANCE", "ACCURACY", "EVIDENCE", "LOGIC"]
    contract_lines = ["VERDICT:", "CONFIDENCE:", "REASONING:", "CONCERNS:", "MET:", "MISSED:"]
    rubric_present = all(t in sample_prompt for t in rubric_terms)
    contract_present = all(line in sample_prompt for line in contract_lines)

    parse_agreement_rate = pct(agree, len(golden))
    no_regression = (
        parse_agreement_rate == 1.0
        and cot_on_genuine_correct == cot_off_genuine_correct
        and cot_on_degenerate_false_pass == 0
        and rubric_present
        and contract_present
    )

    payload = {
        "eval": "judge_cot_goldenset",
        "n_golden": len(golden),
        "parse_agreement_rate": parse_agreement_rate,
        "genuine": {
            "n": n_genuine,
            "cot_off_accuracy": pct(cot_off_genuine_correct, n_genuine),
            "cot_on_accuracy": pct(cot_on_genuine_correct, n_genuine),
        },
        "degenerate": {
            "n": n_degen,
            "cot_on_false_pass": cot_on_degenerate_false_pass,
            "cot_on_false_pass_rate": pct(cot_on_degenerate_false_pass, n_degen),
        },
        "cot_prompt_structural": {
            "rubric_present": rubric_present,
            "output_contract_present": contract_present,
        },
        "no_regression": no_regression,
        "quality_delta_measured": False,
        "quality_delta_note": (
            "Reasoning-quality improvement is NOT measured offline (StubBackend "
            "ignores the prompt). Expected gain is literature-backed "
            "(arXiv:2604.23178), not a number we measured. Run a live golden set "
            "to quantify."
        ),
        "cases": rows,
    }
    return payload


def main() -> dict:
    payload = evaluate()
    path = write_result("judge_cot_goldenset", payload)
    g = payload["genuine"]
    print(f"[judge_cot_goldenset] parse-agreement (CoT on vs off) = "
          f"{payload['parse_agreement_rate']:.0%}  -> no_regression={payload['no_regression']}")
    print(f"[judge_cot_goldenset] genuine accuracy: off={g['cot_off_accuracy']:.0%} "
          f"on={g['cot_on_accuracy']:.0%}; degenerate CoT-on false-PASS="
          f"{payload['degenerate']['cot_on_false_pass_rate']:.0%}")
    print(f"[judge_cot_goldenset] rubric+contract present: "
          f"{payload['cot_prompt_structural']}")
    print(f"[judge_cot_goldenset] quality_delta_measured={payload['quality_delta_measured']} "
          f"(needs a live model)")
    print(f"[judge_cot_goldenset] -> {path}")
    return payload


if __name__ == "__main__":
    main()
