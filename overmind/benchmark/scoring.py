"""Score arm verdicts vs the sealed answer keys (§3 metrics + win condition).

Metrics per arm on the held-out slice:
  * caught_defect_rate  — recall over defect tasks (did the arm flag the defect?)
  * false_alarm_rate    — FPR over clean tasks (did it wrongly flag a correct one?)
  * parity_rate         — correct decisions over reproduction tasks
  * agreement_soundness — of what the arm ACCEPTED, fraction truly clean (guards
                          rubber-stamping: accepting a defect counts against)
  * cost_per_accepted_change — total cost / correctly-accepted count
  * blended             — Niklaus-form score, weights pinned before the run

The scorer is the ONLY component that reads the answer keys.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from overmind.benchmark.tasks import REPRODUCTION


def wilson_ci(successes: int, n: int, *, z: float = 1.96) -> tuple[float, float] | None:
    """Wilson score confidence interval for a proportion (AN — "AI Agents That
    Matter", arXiv:2407.01502: report error bars). Returns (lo, hi) in [0,1], or
    None when n == 0. Wilson (not normal-approx) is well-behaved at small n and
    near 0/1 — appropriate for a modest held-out slice."""
    if n <= 0:
        return None
    p = successes / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round(max(0.0, center - half), 4), round(min(1.0, center + half), 4))

# Pinned weights (declared before any run; never tuned on the held-out split).
LAMBDA_FALSE_ALARM = 1.0
PARITY_WEIGHT = 0.5
COST_WEIGHT = 0.005          # per USD-normalized unit
COST_NORM_USD = 1.0          # normalization anchor for the cost term


@dataclass(slots=True)
class ArmMetrics:
    arm: str
    n: int
    defects: int
    cleans: int
    caught: int
    false_alarms: int
    accepted: int
    accepted_correct: int
    repro_total: int
    repro_correct: int
    total_cost_usd: float

    @property
    def caught_defect_rate(self) -> float | None:
        return None if self.defects == 0 else round(self.caught / self.defects, 4)

    @property
    def caught_defect_ci(self) -> tuple[float, float] | None:
        return wilson_ci(self.caught, self.defects)

    @property
    def false_alarm_rate(self) -> float | None:
        return None if self.cleans == 0 else round(self.false_alarms / self.cleans, 4)

    @property
    def false_alarm_ci(self) -> tuple[float, float] | None:
        return wilson_ci(self.false_alarms, self.cleans)

    @property
    def parity_rate(self) -> float | None:
        return None if self.repro_total == 0 else round(self.repro_correct / self.repro_total, 4)

    @property
    def agreement_soundness(self) -> float | None:
        return None if self.accepted == 0 else round(self.accepted_correct / self.accepted, 4)

    @property
    def cost_per_accepted_change(self) -> float | None:
        return None if self.accepted_correct == 0 else round(self.total_cost_usd / self.accepted_correct, 6)

    @property
    def blended(self) -> float:
        cdr = self.caught_defect_rate or 0.0
        far = self.false_alarm_rate or 0.0
        par = self.parity_rate or 0.0
        cpac = self.cost_per_accepted_change or 0.0
        return round(
            cdr - LAMBDA_FALSE_ALARM * far + PARITY_WEIGHT * par - COST_WEIGHT * (cpac / COST_NORM_USD),
            4,
        )

    def to_dict(self) -> dict:
        return {
            "arm": self.arm, "n": self.n, "defects": self.defects, "cleans": self.cleans,
            "caught": self.caught, "false_alarms": self.false_alarms,
            "caught_defect_rate": self.caught_defect_rate,
            "caught_defect_ci95": self.caught_defect_ci,
            "false_alarm_rate": self.false_alarm_rate,
            "false_alarm_ci95": self.false_alarm_ci,
            "parity_rate": self.parity_rate,
            "agreement_soundness": self.agreement_soundness,
            "accepted": self.accepted, "accepted_correct": self.accepted_correct,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "cost_per_accepted_change": self.cost_per_accepted_change,
            "blended": self.blended,
        }


def score_arm(arm: str, verdicts: dict, keys: dict, costs: dict | None = None) -> ArmMetrics:
    """Score one arm. ``verdicts`` maps task_id -> ArmVerdict; ``keys`` maps
    task_id -> AnswerKey; ``costs`` maps task_id -> usd (optional)."""
    costs = costs or {}
    defects = cleans = caught = false_alarms = 0
    accepted = accepted_correct = 0
    repro_total = repro_correct = 0
    total_cost = 0.0
    for tid, key in keys.items():
        v = verdicts.get(tid)
        if v is None:
            continue
        total_cost += float(costs.get(tid, 0.0))
        has_defect = key.has_defect
        if has_defect:
            defects += 1
            if v.flag:
                caught += 1
        else:
            cleans += 1
            if v.flag:
                false_alarms += 1
        if v.accepted:
            accepted += 1
            if not has_defect:
                accepted_correct += 1
        # parity: reproduction tasks carry a reference_value; a correct decision is
        # flag == has_defect (flag a perturbed estimate, accept a correct one).
        if key.reference_value is not None:
            repro_total += 1
            if v.flag == has_defect:
                repro_correct += 1
    return ArmMetrics(
        arm=arm, n=len([t for t in keys if t in verdicts]),
        defects=defects, cleans=cleans, caught=caught, false_alarms=false_alarms,
        accepted=accepted, accepted_correct=accepted_correct,
        repro_total=repro_total, repro_correct=repro_correct, total_cost_usd=total_cost,
    )


@dataclass(slots=True)
class WinCondition:
    c_beats_a: bool
    c_beats_b: bool
    affordable: bool
    verdict: str
    notes: list[str]

    def to_dict(self) -> dict:
        return {"c_beats_a": self.c_beats_a, "c_beats_b": self.c_beats_b,
                "affordable": self.affordable, "verdict": self.verdict, "notes": self.notes}


@dataclass(slots=True)
class TwoSlicePromotion:
    """AN-2: a harness-evolution candidate is promoted only if it beats the
    incumbent on BOTH the held-out (scored) slice AND the frozen (sealed) slice.
    A win on held-out alone is 'harness updating', not 'harness benefit'
    (arXiv:2605.30621)."""
    held_out_win: bool
    frozen_win: bool
    promote: bool
    reason: str

    def to_dict(self) -> dict:
        return {"held_out_win": self.held_out_win, "frozen_win": self.frozen_win,
                "promote": self.promote, "reason": self.reason}


def two_slice_promotion(incumbent_blended_held_out: float, candidate_blended_held_out: float,
                        incumbent_blended_frozen: float, candidate_blended_frozen: float,
                        *, margin: float = 0.0) -> TwoSlicePromotion:
    """Promote a candidate harness change only if it wins on held-out AND frozen."""
    ho = candidate_blended_held_out > incumbent_blended_held_out + margin
    fr = candidate_blended_frozen > incumbent_blended_frozen + margin
    promote = ho and fr
    if promote:
        reason = "wins on both held-out and frozen (real benefit, not eval-fit)"
    elif ho and not fr:
        reason = "wins on held-out but NOT frozen — likely harness-fit / overfitting the gate; REJECT"
    elif fr and not ho:
        reason = "wins on frozen but not held-out — inconsistent; REJECT"
    else:
        reason = "wins on neither; REJECT"
    return TwoSlicePromotion(ho, fr, promote, reason)


def evaluate_win_condition(a: ArmMetrics, b: ArmMetrics, c: ArmMetrics,
                           *, cost_multiple_k: float = 5.0) -> WinCondition:
    """Truth-first win condition (can report NOT winning).

    C is 'world-class for its purpose' iff:
      1. C > A on caught-defect AND agreement-soundness, false-alarm no worse; and
      2. C > B on caught-defect OR agreement-soundness at <= cost-per-accepted; and
      3. C's cost-per-accepted <= K x A's.
    """
    notes: list[str] = []

    def _ge(x, y):  # None-safe >=
        return (x or 0.0) >= (y or 0.0)

    def _gt(x, y):
        return (x or 0.0) > (y or 0.0)

    c_beats_a = (
        _gt(c.caught_defect_rate, a.caught_defect_rate)
        and _ge(c.agreement_soundness, a.agreement_soundness)
        and _ge(a.false_alarm_rate, c.false_alarm_rate)  # C's FAR no worse (<=) than A's
    )
    if not c_beats_a:
        notes.append("C did NOT beat A on caught-defect + agreement with FAR no worse.")

    c_cpac = c.cost_per_accepted_change or 0.0
    b_cpac = b.cost_per_accepted_change or 0.0
    c_beats_b = (
        (_gt(c.caught_defect_rate, b.caught_defect_rate) or _gt(c.agreement_soundness, b.agreement_soundness))
        and (b_cpac == 0.0 or c_cpac <= b_cpac)
    )
    if not c_beats_b:
        notes.append("C ~ B: vendor diversity not paying at equal-or-lower cost (report honestly).")

    a_cpac = a.cost_per_accepted_change or 0.0
    affordable = (a_cpac == 0.0) or (c_cpac <= cost_multiple_k * a_cpac)
    if not affordable:
        notes.append(f"C cost-per-accepted {c_cpac} > {cost_multiple_k}x A's {a_cpac} — correct but not affordable.")

    verdict = "WORLD_CLASS" if (c_beats_a and c_beats_b and affordable) else "NOT_PROVEN"
    return WinCondition(c_beats_a, c_beats_b, affordable, verdict, notes)
