"""Skill promotion gate — archive + evidence-bundle + benchmark-gated promotion.

Implements two frontier ideas for the evolution subsystem (see memory
`harness-ai-eng-breakthroughs-2026`):

- **Darwin-Gödel-Machine** (arXiv:2505.22954): keep an *archive* of every
  candidate and its outcome; never greedily overwrite/forget a skill. The
  archive is append-only.
- **Audited Skill-Graph** (arXiv:2512.23760): a verifier replays a candidate and
  emits an *evidence bundle* before any promotion decision. Promotion is gated on
  that evidence, not on trust counters alone.

The gate promotes a Skill to ``trusted`` ONLY when an evidence bundle shows it
*actually resolved failures* often enough and the fix *held* (durability) — and
there is at least one real success on record. Trust without real success evidence
never promotes (this mirrors the Verdict-schema lesson that a SKIP/UNVERIFIED is
not a pass: no positive evidence => no promotion).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, List, Optional

# The arbitrator's success set — kept here so callers can map recipe/verdict
# evidence to "real success" consistently with cert_bundle.Arbitrator.
SUCCESS_VERDICTS = ("CERTIFIED", "PASS")


@dataclass
class PromotionPolicy:
    """Thresholds for promoting a candidate skill to trusted."""
    min_uses: int = 5
    min_success_rate: float = 0.8
    min_durability: float = 0.7


@dataclass
class EvidenceBundle:
    """The audit artifact behind a promotion decision (append-only archived)."""
    skill_id: str
    decision: str            # "promote" | "hold" | "reject"
    reason: str
    times_used: int
    times_succeeded: int
    success_rate: float
    durability: float
    policy: dict = field(default_factory=dict)
    ts: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SkillArchive:
    """Append-only archive of promotion decisions (DGM: never overwrite/forget).

    Every promotion/hold/reject/demotion is recorded as one JSON line so the
    full history of a skill's lifecycle survives — even skills that were later
    demoted and deleted from the live library.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def record(self, bundle: "EvidenceBundle | dict") -> None:
        payload = bundle.to_dict() if hasattr(bundle, "to_dict") else dict(bundle)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=True) + "\n")

    def all(self) -> List[dict]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def history(self, skill_id: str) -> List[dict]:
        return [b for b in self.all() if b.get("skill_id") == skill_id]


class PromotionGate:
    """Evaluate skills against a policy, archive the evidence, promote on pass.

    ``clock`` is injectable (callable -> float) so tests and deterministic runs
    don't depend on wall-clock time.

    ``manual_run_required`` (QW-5, default False): when True, a skill is only
    eligible for promotion if it carries ``verified_in_manual_run=True``, set
    by the nightly runner when invoked with ``--manual``.  Default OFF
    preserves current promotion behaviour.
    """

    def __init__(
        self,
        library,
        policy: Optional[PromotionPolicy] = None,
        archive: Optional[SkillArchive] = None,
        *,
        clock=None,
        manual_run_required: bool = False,
    ) -> None:
        self.library = library
        self.policy = policy or PromotionPolicy()
        self.archive = archive
        self._clock = clock or (lambda: 0.0)
        self.manual_run_required = manual_run_required

    def evaluate(self, skill) -> EvidenceBundle:
        """Pure decision: build the evidence bundle for one skill. No side effects."""
        p = self.policy
        uses = skill.times_used
        succeeded = skill.times_succeeded
        sr = skill.success_rate
        dur = skill.durability

        # QW-5: manual-run gate (default OFF — only active when manual_run_required=True)
        if self.manual_run_required and not getattr(skill, "verified_in_manual_run", False):
            return EvidenceBundle(
                skill_id=skill.skill_id,
                decision="hold",
                reason="manual_run_required: skill not yet verified in a --manual run",
                times_used=uses,
                times_succeeded=succeeded,
                success_rate=round(sr, 4),
                durability=round(dur, 4),
                policy=asdict(p),
                ts=self._clock(),
            )

        if uses < p.min_uses:
            decision, reason = "hold", f"needs >={p.min_uses} uses (have {uses})"
        elif succeeded < 1:
            # No positive evidence at all — never promote on zero real successes.
            decision, reason = "hold", "no successful application on record"
        elif sr < p.min_success_rate:
            decision, reason = "reject", f"success_rate {sr:.2f} < min {p.min_success_rate}"
        elif dur < p.min_durability:
            decision, reason = "reject", f"durability {dur:.2f} < min {p.min_durability} (fix not holding)"
        else:
            decision, reason = "promote", (
                f"{succeeded}/{uses} succeeded (rate {sr:.2f}), durability {dur:.2f}"
            )

        return EvidenceBundle(
            skill_id=skill.skill_id,
            decision=decision,
            reason=reason,
            times_used=uses,
            times_succeeded=succeeded,
            success_rate=round(sr, 4),
            durability=round(dur, 4),
            policy=asdict(p),
            ts=self._clock(),
        )

    def maybe_promote(self, skill_id: str) -> EvidenceBundle:
        """Evaluate skill_id, archive the evidence, and promote it if it passes.

        Returns the EvidenceBundle (decision in promote/hold/reject). Archiving
        is append-only; promotion marks the skill trusted in the live library.
        Unknown skill_id yields a 'reject' bundle (fail-closed), still archived.
        """
        skill = self.library.skills.get(skill_id)
        if skill is None:
            bundle = EvidenceBundle(
                skill_id=skill_id, decision="reject",
                reason="no such skill in library",
                times_used=0, times_succeeded=0, success_rate=0.0,
                durability=0.0, policy=asdict(self.policy), ts=self._clock(),
            )
        else:
            bundle = self.evaluate(skill)
        if self.archive is not None:
            self.archive.record(bundle)
        if bundle.decision == "promote":
            self.library.mark_trusted(skill_id, self._clock())
        return bundle

    def sweep(self) -> List[EvidenceBundle]:
        """Evaluate+archive every skill in the library; promote those that pass."""
        return [self.maybe_promote(sid) for sid in list(self.library.skills)]
