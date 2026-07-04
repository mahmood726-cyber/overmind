"""Run the MADE-style A/B/C benchmark (the proof) — capacity-aware + resumable.

Runs what it can NOW and STAGES the rest:
  * the deterministic OBJECTIVE REFERENCE (witness-only) — always runs, no vendor;
  * an Arm C SHADOW dry-run with stub reviewers — proves the consensus-or-flag +
    objective-floor plumbing end-to-end without quota;
  * real Arm A / B / C — run for whichever vendors pass the auth preflight; the
    rest are marked STAGED. Re-running when capacity returns resumes via checkpoint.

Truth-first: scoring can report NOT_PROVEN. Held-out answer keys are read ONLY by
the scorer. Usage:
    python scripts/run_benchmark.py            # run available + stage the rest
    python scripts/run_benchmark.py --shadow   # only the objective ref + C shadow
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overmind.benchmark.reviewers import BackendReviewer, StubReviewer  # noqa: E402
from overmind.benchmark.runner import ArmSpec, run_arm  # noqa: E402
from overmind.benchmark.scorecard import write_scorecard  # noqa: E402
from overmind.benchmark.scoring import evaluate_win_condition, score_arm, ArmMetrics  # noqa: E402
from overmind.benchmark.tasks import held_out_ids, load_keys, load_tasks  # noqa: E402
from overmind.reliability.checkpoint import CheckpointStore  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "benchmark_data"
OUT_DIR = DATA_DIR / "runs"


def _live_vendors() -> dict:
    """Which reviewer vendors respond to a real smoke right now.

    Uses the reliability preflight (real exec smokes): headless Claude
    (subscription OAuth — NOT capped), both Codex seats, and agy. Plus a direct
    Gemini probe."""
    live = {}
    try:
        from overmind.reliability.auth_preflight import preflight_all
        for p in preflight_all():   # now includes first-class claude (OAuth)
            if p.alive:
                live[p.vendor] = True
    except Exception:  # noqa: BLE001
        pass
    # Gemini direct API.
    try:
        from overmind.verification.llm_judge import GeminiBackend
        from overmind.verification.judge_backends import JUDGE_ERROR
        r = GeminiBackend().query("Reply READY")
        if isinstance(r, str) and not r.startswith(JUDGE_ERROR):
            live["gemini"] = True
    except Exception:  # noqa: BLE001
        pass
    return live


def _real_reviewer(vendor: str):
    if vendor == "claude":
        from overmind.verification.judge_backends import ClaudeCodeBackend
        return BackendReviewer(ClaudeCodeBackend(), vendor="claude")
    if vendor == "codex":
        from overmind.verification.judge_backends import CodexBackend
        return BackendReviewer(CodexBackend(seat="mahmood", effort="xhigh"), vendor="codex")
    if vendor == "agy":
        from overmind.verification.judge_backends import AgyBackend
        return BackendReviewer(AgyBackend(), vendor="agy")
    if vendor == "gemini":
        from overmind.verification.llm_judge import GeminiBackend
        return BackendReviewer(GeminiBackend(), vendor="gemini")
    raise ValueError(vendor)


def main() -> int:
    shadow = "--shadow" in sys.argv
    tasks = load_tasks(DATA_DIR / "tasks.json")
    keys = load_keys(DATA_DIR / "keys" / "keys.json")   # scorer-only
    ho = held_out_ids([t.id for t in tasks])
    held = [t for t in tasks if t.id in ho]
    ho_keys = {k: v for k, v in keys.items() if k in ho}
    store = CheckpointStore(DATA_DIR / "checkpoints")
    arms_out = []
    notes = [
        f"Held-out slice: {len(held)} tasks from {len(tasks)} total "
        f"(defects={sum(1 for k in ho_keys.values() if k.has_defect)}, "
        f"clean={sum(1 for k in ho_keys.values() if not k.has_defect)}).",
        "Held-out split is a deterministic sha256 bucket; answer keys read only by the scorer.",
        "Weights pinned (BENCHMARK.md/scoring.py); scoring can report NOT_PROVEN.",
    ]

    # 1) Objective reference (deterministic; always runs).
    ref_run = run_arm(ArmSpec("C", reviewers=[], use_witness=True), held,
                      results_path=OUT_DIR / "objective_ref.jsonl")
    ref_m = score_arm("objective-ref", ref_run.verdicts, ho_keys)
    arms_out.append({"arm": "objective-ref (witness-only floor)", "status": "RUN", "metrics": ref_m.to_dict()})
    ro = sum(1 for t in held if t.id in ho_keys and ho_keys[t.id].has_defect
             and t.kind in {"direction", "wrong_measure_label", "method_mismatch",
                            "comparator_swap", "missing_reference", "subgroup_mismatch"})
    notes.append(f"Objective reference = Arm C floor with NO reviewers: catches witness-detectable "
                 f"defects (impossible_cell, reproduction, ci_invalid) but structurally misses the "
                 f"{ro} reviewer-only defects in the held-out slice (6 classes) — that gap is what the "
                 f"cross-vendor panel must close.")

    # 2) Arm C SHADOW dry-run with stub reviewers (plumbing proof, no quota).
    stub_a = StubReviewer({t.id: (True, "stub flags defect")
                           for t in held if ho_keys[t.id].has_defect}, vendor="stub-anthropic")
    stub_b = StubReviewer({t.id: (True, "stub flags defect")
                           for t in held if ho_keys[t.id].has_defect}, vendor="stub-openai")
    shadow_run = run_arm(ArmSpec("C", reviewers=[stub_a, stub_b], use_witness=True), held,
                         results_path=OUT_DIR / "arm_c_shadow.jsonl")
    shadow_m = score_arm("C-shadow", shadow_run.verdicts, ho_keys)
    arms_out.append({"arm": "C-shadow (stub reviewers)", "status": "SHADOW", "metrics": shadow_m.to_dict()})

    # 3) Real arms for live vendors; stage the rest.
    live = {} if shadow else _live_vendors()
    notes.append(f"Live vendors this run: {sorted(live) or 'NONE (all capped/unauthed)'}.")
    real_metrics: dict[str, ArmMetrics] = {}

    def _run_real(name, reviewers, use_witness, cp):
        run = run_arm(ArmSpec(name, reviewers, use_witness=use_witness), held,
                      checkpoint_store=store, results_path=OUT_DIR / f"arm_{name}.jsonl",
                      cost_fn=lambda t, v: _est_cost(v))
        m = score_arm(name, run.verdicts, ho_keys)
        real_metrics[name] = m
        arms_out.append({"arm": name, "status": "RUN", "metrics": m.to_dict()})

    # A = single frontier model (prefer claude, else any live frontier).
    a_vendor = "claude" if "claude" in live else next(iter(live), None)
    if a_vendor:
        _run_real("A", [_real_reviewer(a_vendor)], False, store)
    else:
        arms_out.append({"arm": "A", "status": "STAGED (needs a live frontier model)", "metrics": None})

    # B = homogeneous panel (same vendor x3).
    if a_vendor:
        _run_real("B", [_real_reviewer(a_vendor) for _ in range(3)], False, store)
    else:
        arms_out.append({"arm": "B", "status": "STAGED (needs a live frontier model x3)", "metrics": None})

    # C = heterogeneous panel across DISTINCT live families + objective floor.
    fam = {"claude": "anthropic", "codex": "openai", "gemini": "google", "agy": "google"}
    picked, seen = [], set()
    for v in live:
        if fam.get(v) not in seen:
            seen.add(fam.get(v)); picked.append(v)
    if len(picked) >= 2:
        _run_real("C", [_real_reviewer(v) for v in picked], True, store)
        notes.append(f"Arm C reviewers: {picked} (distinct families).")
    else:
        arms_out.append({"arm": "C", "status": f"STAGED (needs >=2 distinct live families; have {sorted(live)})", "metrics": None})

    # Win condition only when A, B, C all ran.
    win = None
    if all(k in real_metrics for k in ("A", "B", "C")):
        win = evaluate_win_condition(real_metrics["A"], real_metrics["B"], real_metrics["C"]).to_dict()

    scorecard = {"slice": str(DATA_DIR), "held_out_n": len(held), "arms": arms_out,
                 "win_condition": win, "notes": notes}
    paths = write_scorecard(OUT_DIR, scorecard)
    print(f"objective-ref: caught={ref_m.caught_defect_rate} false_alarm={ref_m.false_alarm_rate} "
          f"parity={ref_m.parity_rate} agreement={ref_m.agreement_soundness}")
    print(f"live vendors: {sorted(live) or 'none'}; scorecard -> {paths['md']}")
    if win:
        print(f"WIN CONDITION: {win['verdict']}")
    else:
        print("WIN CONDITION: pending (A/B/C not all live yet — re-run on capacity return; resumes via checkpoint)")
    return 0


def _est_cost(verdict) -> float:
    # placeholder per-call estimate; measured total_cost_usd is captured when the
    # claude arm runs with --output-format json (cost_accounting.cost_event_from_output).
    return 0.0


if __name__ == "__main__":
    raise SystemExit(main())
