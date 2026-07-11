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
    accepted: bool                # accepts as clean (not flag AND not abstained)
    deciding: str                 # what drove it (witness / consensus / reviewer / majority / abstain)
    reviewer_flags: list[bool] = field(default_factory=list)
    witness_defect: bool | None = None
    abstained: bool = False       # conformal gate declined to judge (neither flag nor accept)

    def to_dict(self) -> dict:
        return {"task_id": self.task_id, "arm": self.arm, "flag": self.flag,
                "accepted": self.accepted, "deciding": self.deciding,
                "reviewer_flags": list(self.reviewer_flags), "witness_defect": self.witness_defect,
                "abstained": self.abstained}


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


def arm_c(task_id: str, reviewer_verdicts: list, witness_defect: bool, gate=None) -> ArmVerdict:
    """Heterogeneous consensus-or-flag + objective-gate floor (D1+D2), with an
    optional conformal accept/abstain gate (PV-B).

    The witness is the FLOOR: a deterministic defect flags regardless of reviewers
    and is NEVER abstained. Otherwise reviewers must unanimously agree "clean" to
    accept; any flag or any disagreement -> flag. When a ``gate`` is supplied, a
    reviewer-driven flag whose confidence is below the gate's calibrated threshold
    is converted to an ABSTENTION (neither flag nor accept) — a borderline
    significance/degeneracy objection declines to judge instead of crying wolf.
    Passing ``gate=None`` (the default) keeps the pre-gate behavior byte-for-byte."""
    flags = [bool(v.flag) for v in reviewer_verdicts]
    if witness_defect:
        return ArmVerdict(task_id, "C", True, False, "objective_gate_floor", flags, True)
    if not flags:
        # no reviewers reached (e.g. all vendors degraded): witness clean -> accept,
        # but mark deciding so the report shows there was no cross-vendor corroboration.
        return ArmVerdict(task_id, "C", False, True, "witness_only_no_reviewers", flags, False)
    if any(flags):
        # a reviewer-driven flag: consult the conformal gate (if any) before asserting.
        if gate is not None and gate.should_abstain(reviewer_verdicts):
            return ArmVerdict(task_id, "C", False, False, "conformal_abstain", flags, False,
                              abstained=True)
        return ArmVerdict(task_id, "C", True, False, "consensus_or_flag(review_flag)", flags, False)
    # all reviewers agree clean AND witness clean
    return ArmVerdict(task_id, "C", False, True, "consensus_clean+witness_clean", flags, False)


def arm_c_corroborated(task_id: str, reviewer_verdicts: list, witness_defect: bool) -> ArmVerdict:
    """Heterogeneous panel with SCOPED corroboration (PV-C, precision fix #2).

    Identical to ``arm_c`` EXCEPT for one relaxation of flag-on-any-dissent, applied
    *only* to borderline flags:

      * **witness floor** — a deterministic defect always flags (fail-closed, never
        relaxed).
      * **structural dissent** — if ANY usable reviewer cites a concrete structural /
        arithmetic defect (mislabel, comparator swap, missing arm, method/heterogeneity
        mismatch, subgroup mismatch, impossible cell, transposed CI, reproduction
        mismatch), the panel flags on that single dissent — **fail-closed preserved**
        for the entire hard/high-severity class.
      * **borderline (sig-only) flag** — a flag that rests ONLY on a
        significance/degeneracy objection (CI crosses the null, non-significant, zero
        events, "not estimable") is relaxed: it flags **only if >= 2 distinct vendors
        corroborate it**. A lone significance objection (one vendor flags, the other
        accepts) is NOT a defect — it accepts.

    Where fail-closed is preserved: the witness floor and every structural defect
    (any single dissent still flags). Where it is relaxed: single-vendor
    significance-only objections on data that passes every deterministic check. This
    is exactly the false-alarm class from the live run (agy's CI-crosses-1 over-read)
    — never a hard defect. ``arm_c`` is unchanged; this is a separate, opt-in path so
    the harness default is byte-for-byte identical until promoted."""
    from overmind.benchmark.conformal import panel_signals
    flags = [bool(v.flag) for v in reviewer_verdicts]
    if witness_defect:
        return ArmVerdict(task_id, "C", True, False, "objective_gate_floor", flags, True)
    sig = panel_signals(reviewer_verdicts)
    if sig.n_flag_vendors == 0:
        # no usable reviewer flagged -> accept (mirrors arm_c's clean/empty branches)
        deciding = "witness_only_no_reviewers" if not flags else "consensus_clean+witness_clean"
        return ArmVerdict(task_id, "C", False, True, deciding, flags, False)
    if sig.any_structural:
        # fail-closed: a structural defect flags on any single dissent, as in arm_c.
        return ArmVerdict(task_id, "C", True, False, "structural_flag(any_dissent)", flags, False)
    # all flaggers are significance/degeneracy-only -> require >=2 vendors to corroborate.
    if sig.n_flag_vendors >= 2:
        return ArmVerdict(task_id, "C", True, False,
                          f"corroborated_borderline({sig.n_flag_vendors}v)", flags, False)
    return ArmVerdict(task_id, "C", False, True, "uncorroborated_borderline->accept", flags, False)
