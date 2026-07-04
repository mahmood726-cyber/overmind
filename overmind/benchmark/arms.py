"""The three arms: single-agent (A), homogeneous (B), heterogeneous truth-gated (C).

Each arm turns per-reviewer verdicts (+ for C, the objective witness) into one
ArmVerdict: ``flag`` (defect asserted) and ``accepted`` (= not flag). The arms
differ ONLY in aggregation, so the head-to-head isolates the panel design:

  A — single reviewer's flag.
  B — majority flag across a same-vendor panel (more agents, no vendor diversity,
      no objective floor).
  C — heterogeneous consensus-or-flag WITH the D2 objective-gate floor:
        * the deterministic witness can force a flag beneath any "accept";
        * reviewers must UNANIMOUSLY agree "clean" to accept — any flag or any
          disagreement flags (consensus-or-flag).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ArmVerdict:
    task_id: str
    arm: str
    flag: bool                    # arm asserts a defect
    accepted: bool                # not flag
    deciding: str                 # what drove it (witness / consensus / reviewer / majority)
    reviewer_flags: list[bool] = field(default_factory=list)
    witness_defect: bool | None = None

    def to_dict(self) -> dict:
        return {"task_id": self.task_id, "arm": self.arm, "flag": self.flag,
                "accepted": self.accepted, "deciding": self.deciding,
                "reviewer_flags": list(self.reviewer_flags), "witness_defect": self.witness_defect}


def arm_a(task_id: str, reviewer_verdicts: list) -> ArmVerdict:
    """Single-agent: the (one) reviewer's flag decides."""
    flags = [bool(v.flag) for v in reviewer_verdicts]
    flag = flags[0] if flags else False
    return ArmVerdict(task_id, "A", flag, not flag, "single_reviewer", flags, None)


def arm_b(task_id: str, reviewer_verdicts: list) -> ArmVerdict:
    """Homogeneous panel: majority flag (ties -> flag, conservative). No floor."""
    flags = [bool(v.flag) for v in reviewer_verdicts]
    if not flags:
        return ArmVerdict(task_id, "B", False, True, "empty_panel", flags, None)
    votes_flag = sum(flags)
    flag = votes_flag * 2 >= len(flags)  # >= half -> flag (tie flags)
    return ArmVerdict(task_id, "B", flag, not flag, f"majority({votes_flag}/{len(flags)})", flags, None)


def arm_c(task_id: str, reviewer_verdicts: list, witness_defect: bool) -> ArmVerdict:
    """Heterogeneous consensus-or-flag + objective-gate floor (D1+D2).

    The witness is the FLOOR: a deterministic defect flags regardless of reviewers.
    Otherwise reviewers must unanimously agree "clean" to accept; any flag or any
    disagreement -> flag."""
    flags = [bool(v.flag) for v in reviewer_verdicts]
    if witness_defect:
        return ArmVerdict(task_id, "C", True, False, "objective_gate_floor", flags, True)
    if not flags:
        # no reviewers reached (e.g. all vendors degraded): witness clean -> accept,
        # but mark deciding so the report shows there was no cross-vendor corroboration.
        return ArmVerdict(task_id, "C", False, True, "witness_only_no_reviewers", flags, False)
    if any(flags):
        return ArmVerdict(task_id, "C", True, False, "consensus_or_flag(review_flag)", flags, False)
    # all reviewers agree clean AND witness clean
    return ArmVerdict(task_id, "C", False, True, "consensus_clean+witness_clean", flags, False)
