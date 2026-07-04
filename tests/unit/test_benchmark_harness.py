"""End-to-end tests for the benchmark harness (§3) using deterministic stub
reviewers — no quota. Proves: witnesses, arms A/B/C aggregation, scoring +
win-condition (incl. the honest NOT-winning outcomes), and checkpoint/resume.
"""
from __future__ import annotations

from overmind.benchmark.arms import arm_a, arm_b, arm_c
from overmind.benchmark.reviewers import ReviewerVerdict, StubReviewer, parse_reviewer_output
from overmind.benchmark.runner import ArmSpec, run_arm
from overmind.benchmark.scoring import evaluate_win_condition, score_arm
from overmind.benchmark.tasks import (
    AnswerKey,
    Task,
    CLEAN,
    DIRECTION,
    IMPOSSIBLE_CELL,
    REPRODUCTION,
    held_out_ids,
    stable_bucket,
)
from overmind.benchmark.witnesses import impossible_cell_witness, reproduction_witness, run_witness
from overmind.reliability.checkpoint import CheckpointStore


# --- witnesses ------------------------------------------------------------------

def test_impossible_cell_witness_flags():
    data = {"studies": [{"label": "S1", "ai": 524, "n1": 39, "ci": 5, "n2": 40}]}
    assert impossible_cell_witness(data).defect is True


def test_impossible_cell_witness_clean():
    data = {"studies": [{"label": "S1", "ai": 4, "n1": 123, "ci": 11, "n2": 139}]}
    assert impossible_cell_witness(data).defect is False


def test_reproduction_witness_detects_wrong_estimate():
    # real BCG-ish data; claim a wildly wrong RR
    data = {
        "measure": "RR", "method": "REML", "claimed_value": 2.5, "tolerance": 0.05,
        "studies": [
            {"ai": 4, "n1": 123, "ci": 11, "n2": 139},
            {"ai": 6, "n1": 306, "ci": 29, "n2": 303},
            {"ai": 3, "n1": 231, "ci": 11, "n2": 220},
        ],
    }
    res = reproduction_witness(data)
    assert res.defect is True
    assert res.computed_value is not None and res.computed_value < 1.0  # protective RR


def test_reproduction_witness_accepts_correct_estimate():
    from overmind.evidence.pooling import Study, pool
    studies = [
        {"ai": 4, "n1": 123, "ci": 11, "n2": 139},
        {"ai": 6, "n1": 306, "ci": 29, "n2": 303},
        {"ai": 3, "n1": 231, "ci": 11, "n2": 220},
    ]
    ref = pool([Study(**s) for s in studies], measure="RR", method="REML")["estimate_ratio"]
    data = {"measure": "RR", "method": "REML", "tolerance": 0.05,
            "claimed_value": round(ref, 4), "studies": studies}
    assert reproduction_witness(data).defect is False


# --- held-out split -------------------------------------------------------------

def test_held_out_split_deterministic():
    ids = [f"t{i}" for i in range(200)]
    a = held_out_ids(ids)
    b = held_out_ids(ids)
    assert a == b
    assert 0 < len(a) < len(ids)          # a real split, not all/none


def test_two_slice_frozen_split_disjoint_and_covers():
    from overmind.benchmark.tasks import dev_ids, frozen_ids, held_out_ids
    ids = [f"t{i}" for i in range(500)]
    dev, ho, fz = dev_ids(ids), held_out_ids(ids), frozen_ids(ids)
    # pairwise disjoint
    assert dev & ho == set() and dev & fz == set() and ho & fz == set()
    # cover everything
    assert dev | ho | fz == set(ids)
    # each non-empty and roughly the intended proportions
    assert len(fz) > 0 and len(ho) > 0 and len(dev) > 0
    assert 0.15 < len(fz) / len(ids) < 0.35     # ~0.25 frozen


def test_frozen_slice_deterministic():
    from overmind.benchmark.tasks import frozen_ids
    ids = [f"t{i}" for i in range(300)]
    assert frozen_ids(ids) == frozen_ids(ids)


def test_two_slice_promotion_requires_both():
    from overmind.benchmark.scoring import two_slice_promotion
    # wins both -> promote
    assert two_slice_promotion(1.0, 1.2, 1.0, 1.1).promote is True
    # wins held-out only -> REJECT (harness-fit)
    p = two_slice_promotion(1.0, 1.2, 1.0, 0.9)
    assert p.promote is False and "overfitting" in p.reason
    # wins frozen only -> reject
    assert two_slice_promotion(1.0, 0.9, 1.0, 1.2).promote is False
    # wins neither -> reject
    assert two_slice_promotion(1.0, 0.9, 1.0, 0.9).promote is False


def test_stable_bucket_range():
    assert 0.0 <= stable_bucket("x") < 1.0


# --- arms -----------------------------------------------------------------------

def _rv(flag):
    return ReviewerVerdict(flag=flag)


def test_arm_a_single():
    assert arm_a("t", [_rv(True)]).flag is True
    assert arm_a("t", [_rv(False)]).accepted is True


def test_arm_b_majority():
    assert arm_b("t", [_rv(True), _rv(True), _rv(False)]).flag is True   # 2/3
    assert arm_b("t", [_rv(False), _rv(False), _rv(True)]).flag is False  # 1/3


def test_arm_c_objective_floor_overrides_reviewers():
    # all reviewers say clean, but the witness found a defect -> C flags (floor)
    v = arm_c("t", [_rv(False), _rv(False)], witness_defect=True)
    assert v.flag is True
    assert v.deciding == "objective_gate_floor"


def test_arm_c_consensus_or_flag():
    # reviewers disagree, witness clean -> flag (consensus-or-flag)
    v = arm_c("t", [_rv(True), _rv(False)], witness_defect=False)
    assert v.flag is True
    # all clean + witness clean -> accept
    assert arm_c("t", [_rv(False), _rv(False)], witness_defect=False).accepted is True


# --- reviewer parsing -----------------------------------------------------------

def test_parse_reviewer_output():
    v = parse_reviewer_output("FLAG: yes\nREASON: events exceed N\nVALUE: 0.49")
    assert v.flag is True and v.value == 0.49 and "events" in v.reason


def test_parse_reviewer_empty_is_no_flag():
    assert parse_reviewer_output("").flag is False


# --- scoring + win condition (incl. NOT-winning) --------------------------------

def _tasks_and_keys():
    tasks = [
        Task("d1", IMPOSSIBLE_CELL, "impossible", data={"studies": [{"ai": 99, "n1": 10}]}),
        Task("d2", DIRECTION, "wrong direction", data={}),
        Task("c1", CLEAN, "fine", data={}),
        Task("r1", REPRODUCTION, "claimed 2.5", data={}),
    ]
    keys = {
        "d1": AnswerKey("d1", True, "impossible_cell"),
        "d2": AnswerKey("d2", True, "wrong_direction"),
        "c1": AnswerKey("c1", False),
        "r1": AnswerKey("r1", True, "wrong_pooled_estimate", reference_value=0.49, tolerance=0.05),
    }
    return tasks, keys


def test_score_arm_perfect():
    _, keys = _tasks_and_keys()
    from overmind.benchmark.arms import ArmVerdict
    verdicts = {
        "d1": ArmVerdict("d1", "C", True, False, "x"),
        "d2": ArmVerdict("d2", "C", True, False, "x"),
        "c1": ArmVerdict("c1", "C", False, True, "x"),
        "r1": ArmVerdict("r1", "C", True, False, "x"),
    }
    m = score_arm("C", verdicts, keys)
    assert m.caught_defect_rate == 1.0
    assert m.false_alarm_rate == 0.0
    assert m.parity_rate == 1.0
    assert m.agreement_soundness == 1.0   # accepted c1, which was clean


def test_score_arm_rubber_stamp_penalized():
    _, keys = _tasks_and_keys()
    from overmind.benchmark.arms import ArmVerdict
    # accepts everything (misses all defects) -> agreement_soundness low
    verdicts = {tid: __import__("overmind.benchmark.arms", fromlist=["ArmVerdict"]).ArmVerdict(tid, "A", False, True, "x")
                for tid in keys}
    m = score_arm("A", verdicts, keys)
    assert m.caught_defect_rate == 0.0
    assert m.agreement_soundness < 0.5    # accepted 3 defects + 1 clean


def test_win_condition_can_report_not_winning():
    from overmind.benchmark.scoring import ArmMetrics
    # B == C (homogeneous already perfect) -> C does not beat B -> NOT_PROVEN
    perfect = dict(defects=2, cleans=2, caught=2, false_alarms=0, accepted=2,
                   accepted_correct=2, repro_total=1, repro_correct=1, total_cost_usd=1.0, n=4)
    a = ArmMetrics(arm="A", **perfect)
    b = ArmMetrics(arm="B", **perfect)
    c = ArmMetrics(arm="C", **perfect)
    wc = evaluate_win_condition(a, b, c)
    assert wc.verdict == "NOT_PROVEN"
    assert any("diversity not paying" in n for n in wc.notes)


# --- runner + checkpoint/resume -------------------------------------------------

def test_run_arm_with_stub_and_checkpoint(tmp_path):
    tasks = [
        Task("d1", IMPOSSIBLE_CELL, "a", data={"studies": [{"ai": 99, "n1": 10}]}),
        Task("c1", CLEAN, "b", data={}),
    ]
    reviewer = StubReviewer({"d1": (True, "impossible")}, vendor="claude")
    spec = ArmSpec("A", [reviewer])
    store = CheckpointStore(tmp_path / "cp")
    results = tmp_path / "results_A.jsonl"
    run = run_arm(spec, tasks, checkpoint_store=store, results_path=results, cost_fn=lambda t, v: 0.01)
    assert run.verdicts["d1"].flag is True
    assert run.verdicts["c1"].accepted is True
    assert store.is_done("benchmark-arm-A", "d1")
    # resume: a second call does no new work (all checkpointed) and keeps verdicts
    run2 = run_arm(spec, tasks, checkpoint_store=store, results_path=results, cost_fn=lambda t, v: 0.01)
    assert set(run2.verdicts) == {"d1", "c1"}


def test_run_arm_c_uses_witness_floor(tmp_path):
    # reviewer says clean, but the witness catches the impossible cell -> C flags
    tasks = [Task("d1", IMPOSSIBLE_CELL, "a", data={"studies": [{"ai": 99, "n1": 10}]})]
    reviewer = StubReviewer({}, vendor="claude")   # sees nothing
    spec = ArmSpec("C", [reviewer], use_witness=True)
    run = run_arm(spec, tasks, results_path=tmp_path / "r.jsonl")
    assert run.verdicts["d1"].flag is True
    assert run.verdicts["d1"].deciding == "objective_gate_floor"


# --- generator + scorecard ------------------------------------------------------

def test_generate_produces_balanced_slice():
    from overmind.benchmark.generate import generate
    from overmind.benchmark.tasks import ALL_KINDS
    tasks, keys = generate(max_fixtures=3)
    assert len(tasks) == len(keys) == 30   # 3 fixtures x 10 kinds
    assert {t.kind for t in tasks} == set(ALL_KINDS)
    kd = {k.id: k for k in keys}
    for t in tasks:
        assert kd[t.id].has_defect == (t.kind != CLEAN)


def test_witness_integrity_fires_only_on_witness_detectable():
    # THE honesty property: the kind-agnostic battery fires EXACTLY on
    # witness-detectable kinds, and NEVER on reviewer-only or clean tasks (so
    # reviewer-only defects genuinely pass the floor -> only a reviewer catches them).
    from overmind.benchmark.generate import generate
    from overmind.benchmark.tasks import WITNESS_DETECTABLE_KINDS
    tasks, _ = generate(max_fixtures=5)
    for t in tasks:
        assert run_witness(t).defect == (t.kind in WITNESS_DETECTABLE_KINDS), t.id


def test_reviewer_only_kinds_pass_all_witnesses():
    from overmind.benchmark.generate import generate
    from overmind.benchmark.tasks import REVIEWER_ONLY_KINDS
    tasks, keys = generate(max_fixtures=6)
    kd = {k.id: k for k in keys}
    ro = [t for t in tasks if t.kind in REVIEWER_ONLY_KINDS]
    assert ro, "expected reviewer-only tasks"
    for t in ro:
        assert kd[t.id].has_defect is True          # it IS a defect
        assert run_witness(t).defect is False        # but the floor cannot see it


def test_scorecard_render():
    from overmind.benchmark.scorecard import render_markdown
    sc = {"slice": "x", "held_out_n": 10,
          "arms": [{"arm": "objective-ref", "status": "RUN",
                    "metrics": {"caught_defect_rate": 0.65, "false_alarm_rate": 0.0,
                                "parity_rate": 1.0, "agreement_soundness": 0.5,
                                "accepted": 5, "cost_per_accepted_change": 0.0, "blended": 1.15}}],
          "win_condition": None, "notes": ["a note"]}
    md = render_markdown(sc)
    assert "objective-ref" in md and "Pending" in md and "a note" in md
