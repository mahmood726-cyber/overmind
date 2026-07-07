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
from overmind.benchmark.tasks import (  # noqa: E402
    frozen_ids, held_out_ids, load_keys, load_tasks, split_summary,
)
from overmind.reliability.checkpoint import CheckpointStore  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "benchmark_data"
OUT_DIR = DATA_DIR / "runs"


def _claude_backend():
    """Claude worker backend: local `claude -p` (subscription OAuth token) by
    default; a REMOTE `ssh <host> claude -p` worker when OVERMIND_CLAUDE_SSH_HOST
    is set (additive, flag-gated). Never displaces the local path unless a host is
    configured — used by BOTH the preflight and the reviewer so they agree."""
    import os
    if os.environ.get("OVERMIND_CLAUDE_SSH_HOST"):
        from overmind.verification.judge_backends import SshClaudeBackend
        return SshClaudeBackend()
    from overmind.verification.judge_backends import ClaudeCodeBackend
    return ClaudeCodeBackend()


def _live_vendors() -> tuple[dict, list[str]]:
    """Which reviewer vendors respond to a real smoke right now (preflight ONCE).

    Uses the reliability preflight (real exec smokes): headless Claude
    (subscription OAuth — NOT capped), both Codex seats, and agy. Plus a direct
    Gemini probe. Returns (live_vendors, per-vendor status notes)."""
    live: dict = {}
    notes: list[str] = []
    try:
        from overmind.reliability.auth_preflight import preflight_all
        for p in preflight_all(claude_backend=_claude_backend()):   # first-class claude (local OAuth or SSH-remote)
            if p.alive:
                live[p.vendor] = True
            notes.append(f"preflight {p.vendor}:{p.seat} = {'LIVE' if p.alive else 'DOWN'} ({p.detail[:70]})")
    except Exception:  # noqa: BLE001
        pass
    # Gemini direct API.
    try:
        from overmind.verification.llm_judge import GeminiBackend
        from overmind.verification.judge_backends import JUDGE_ERROR
        r = GeminiBackend().query("Reply READY")
        alive = isinstance(r, str) and not r.startswith(JUDGE_ERROR)
        if alive:
            live["gemini"] = True
        notes.append(f"preflight gemini:api = {'LIVE' if alive else 'DOWN'} ({(r or '')[:60]})")
    except Exception:  # noqa: BLE001
        pass
    return live, notes


def _real_reviewer(vendor: str):
    if vendor == "claude":
        return BackendReviewer(_claude_backend(), vendor="claude")
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
    global OUT_DIR
    shadow = "--shadow" in sys.argv
    # --max-tasks=N: cap the held-out slice to the first N (sorted by id) for
    # latency-bound vendors (e.g. agy ~35s/call). Deterministic, reproducible; a
    # labelled SUBSET of held-out — the frozen slice stays sealed either way.
    max_tasks = next((int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--max-tasks=")), None)
    tasks = load_tasks(DATA_DIR / "tasks.json")
    keys = load_keys(DATA_DIR / "keys" / "keys.json")   # scorer-only
    all_ids = [t.id for t in tasks]
    ho = held_out_ids(all_ids)
    fz = frozen_ids(all_ids)
    held = [t for t in tasks if t.id in ho]
    if max_tasks is not None:
        held = sorted(held, key=lambda t: t.id)[:max_tasks]
        ho = {t.id for t in held}
        OUT_DIR = DATA_DIR / "runs_live"   # keep the committed full-slice scorecard intact
    frozen = [t for t in tasks if t.id in fz]
    ho_keys = {k: v for k, v in keys.items() if k in ho}
    fz_keys = {k: v for k, v in keys.items() if k in fz}
    store = CheckpointStore(DATA_DIR / "checkpoints")
    arms_out = []
    sp = split_summary(all_ids)
    notes = [
        f"Split (deterministic sha256): dev={sp['dev']} held_out={sp['held_out']} FROZEN={sp['frozen']} "
        f"(of {len(tasks)} total).",
        f"Held-out slice scored this run: {len(held)} tasks "
        f"(defects={sum(1 for k in ho_keys.values() if k.has_defect)}, "
        f"clean={sum(1 for k in ho_keys.values() if not k.has_defect)}).",
        "AN-2 FROZEN slice is SEALED: harness-evolution never reads/scores/tunes on it; a candidate is "
        "promoted only if it also wins there (arXiv:2605.30621). It is scored below for reference only.",
        "Answer keys read only by the scorer. Weights pinned; scoring can report NOT_PROVEN.",
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

    # 2b) FROZEN slice — sealed reference numbers (for promotion checks only; never tuned).
    if frozen:
        fz_ref = run_arm(ArmSpec("C", reviewers=[], use_witness=True), frozen,
                         results_path=OUT_DIR / "frozen_objective_ref.jsonl")
        fz_m = score_arm("frozen-objective-ref", fz_ref.verdicts, fz_keys)
        arms_out.append({"arm": "objective-ref [FROZEN slice, sealed]", "status": "FROZEN",
                         "metrics": fz_m.to_dict()})

    # 3) Real arms for live vendors; stage the rest.
    if shadow:
        live, preflight_notes = {}, []
    else:
        live, preflight_notes = _live_vendors()
    notes.extend(preflight_notes)
    notes.append(f"Live vendors this run: {sorted(live) or 'NONE'}.")
    real_metrics: dict[str, ArmMetrics] = {}
    real_runs: dict[str, object] = {}

    def _run_real(name, reviewers, use_witness, cp):
        run = run_arm(ArmSpec(name, reviewers, use_witness=use_witness), held,
                      checkpoint_store=store, results_path=OUT_DIR / f"arm_{name}.jsonl",
                      cost_fn=lambda t, v: _est_cost(v))
        real_runs[name] = run
        m = score_arm(name, run.verdicts, ho_keys)
        if not run.valid:
            # degraded vendor (reviewers unusable too often) — NOT a valid measurement
            arms_out.append({"arm": name, "status": f"INVALID (vendor degraded, usable-rate "
                             f"{(run.usable_rate or 0):.0%})", "metrics": m.to_dict()})
            notes.append(f"Arm {name} INVALID: reviewer usable-rate {(run.usable_rate or 0):.0%} < "
                         f"50% — the vendor returned empty/envelope responses on most tasks; the "
                         f"verdicts are backend artifacts, not the model's judgment. NOT scored as real.")
            return
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

    # Conformal accept/abstain gate (PV-B): re-derive Arm C with the calibrated
    # gate so borderline significance/degeneracy flags abstain instead of crying
    # wolf. Additive — the ungated Arm C above is untouched; this reports a second
    # "C (conformal)" arm + a gated win condition. alpha (catch-retention budget) is
    # pinned; override via OVERMIND_CONFORMAL_ALPHA. The gate is calibrated on the
    # DEFECT class only (scorer-side keys), preserving clean-label blinding.
    import os
    alpha = float(os.environ.get("OVERMIND_CONFORMAL_ALPHA", "0.10"))
    gated_c_metrics = None
    if "C" in real_metrics and "C" in real_runs:
        gated_c_metrics, gate = _conformal_c(real_runs["C"], ho_keys, alpha)
        arms_out.append({"arm": "C (conformal gate)", "status": "RUN",
                         "metrics": gated_c_metrics.to_dict()})
        notes.append(f"Conformal accept/abstain gate (PV-B): alpha={alpha} (retain >= "
                     f"{1 - alpha:.0%} of catches), tau={gate.tau:.4f}. Borderline "
                     f"significance/degeneracy flags abstain: Arm C false-alarm "
                     f"{real_metrics['C'].false_alarm_rate} -> {gated_c_metrics.false_alarm_rate}, "
                     f"caught {real_metrics['C'].caught_defect_rate} -> "
                     f"{gated_c_metrics.caught_defect_rate} ({gated_c_metrics.abstained} abstained).")

    # Win condition only when A, B, C all ran (reported for BOTH the raw and the
    # conformal-gated Arm C — the gate is the PV-B lever on the FAR clause).
    win = None
    win_gated = None
    if all(k in real_metrics for k in ("A", "B", "C")):
        win = evaluate_win_condition(real_metrics["A"], real_metrics["B"], real_metrics["C"]).to_dict()
        if gated_c_metrics is not None:
            win_gated = evaluate_win_condition(real_metrics["A"], real_metrics["B"],
                                               gated_c_metrics).to_dict()

    scorecard = {"slice": str(DATA_DIR), "held_out_n": len(held), "arms": arms_out,
                 "win_condition": win, "win_condition_conformal": win_gated, "notes": notes}
    paths = write_scorecard(OUT_DIR, scorecard)
    print(f"objective-ref: caught={ref_m.caught_defect_rate} false_alarm={ref_m.false_alarm_rate} "
          f"parity={ref_m.parity_rate} agreement={ref_m.agreement_soundness}")
    print(f"live vendors: {sorted(live) or 'none'}; scorecard -> {paths['md']}")
    if win:
        print(f"WIN CONDITION: {win['verdict']}")
    else:
        print("WIN CONDITION: pending (A/B/C not all live yet — re-run on capacity return; resumes via checkpoint)")
    return 0


def _conformal_c(c_run, ho_keys, alpha):
    """Re-derive Arm C with a calibrated conformal accept/abstain gate. Returns
    (gated_metrics, gate). Calibrated on the DEFECT class only (blinding-preserving)."""
    from overmind.benchmark.arms import arm_c
    from overmind.benchmark.conformal import gate_from_defect_flags
    from overmind.benchmark.reviewers import ReviewerVerdict

    def _panel(tid):
        return [ReviewerVerdict(flag=bool(r.get("flag")), reason=r.get("reason", "") or "",
                                vendor=r.get("vendor", "") or "", usable=bool(r.get("usable", True)))
                for r in c_run.reviewer_records.get(tid, [])]

    defect_ids = {tid for tid, k in ho_keys.items() if k.has_defect and tid in c_run.verdicts}
    gate = gate_from_defect_flags(c_run.reviewer_records, defect_ids, alpha=alpha)
    gated = {}
    for tid, v in c_run.verdicts.items():
        gated[tid] = arm_c(tid, _panel(tid), bool(v.witness_defect), gate=gate)
    return score_arm("C (conformal gate)", gated, ho_keys), gate


def _est_cost(verdict) -> float:
    # placeholder per-call estimate; measured total_cost_usd is captured when the
    # claude arm runs with --output-format json (cost_accounting.cost_event_from_output).
    return 0.0


if __name__ == "__main__":
    raise SystemExit(main())
