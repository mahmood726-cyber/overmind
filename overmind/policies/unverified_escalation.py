"""UNVERIFIED escalation policy — surfaces stale or excessive UNVERIFIED verdicts.

UNVERIFIED is a real verdict in the Overmind taxonomy (see cert_bundle.Arbitrator
lines 77-90): test + smoke PASS but the numerical witness SKIPPED because the
baseline is missing. Per testing.md and the 2026-05-06 SKIP-as-pass-incident
fix, UNVERIFIED is NOT a release pass — it indicates an incomplete tier-3
verification profile.

The verdict engine writes UNVERIFIED correctly. What's been missing is
*escalation* — surfacing UNVERIFIED projects that have sat in that state for
weeks without anyone noticing (the missing baseline never got created). This
module adds two policy-controlled signals to the nightly markdown report:

  1. **age-based escalation**: any UNVERIFIED project whose verdict has been
     UNVERIFIED for more than `age_threshold_days` (default 14) is listed in
     a separate "Escalations" section with the days-since-first-UNVERIFIED count.

  2. **count-based attention prefix**: if the portfolio has more than
     `count_threshold` UNVERIFIED projects (default 5), the nightly report
     header gets a `[ATTENTION]` prefix so the operator-facing dashboard /
     digest visibly flags the backlog.

Neither signal changes the verdict computation. Both are additive surface area.

Configurable via env var (no config file dependency for Phase 1):
  - OVERMIND_UNVERIFIED_AGE_DAYS   (default 14)
  - OVERMIND_UNVERIFIED_COUNT      (default 5)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_AGE_THRESHOLD_DAYS = 14
DEFAULT_COUNT_THRESHOLD = 5


@dataclass(frozen=True)
class UnverifiedPolicy:
    age_threshold_days: int = DEFAULT_AGE_THRESHOLD_DAYS
    count_threshold: int = DEFAULT_COUNT_THRESHOLD

    @classmethod
    def from_env(cls) -> "UnverifiedPolicy":
        return cls(
            age_threshold_days=int(os.environ.get(
                "OVERMIND_UNVERIFIED_AGE_DAYS", DEFAULT_AGE_THRESHOLD_DAYS)),
            count_threshold=int(os.environ.get(
                "OVERMIND_UNVERIFIED_COUNT", DEFAULT_COUNT_THRESHOLD)),
        )


@dataclass
class EscalatedProject:
    project_name: str
    first_unverified_at: datetime
    days_unverified: int
    arbitration_reason: str


def find_first_unverified_date(
    project_name: str,
    bundles_root: Path,
) -> datetime | None:
    """Walk historical nightly bundles to find the earliest date this project
    was UNVERIFIED. Returns None if no historical bundle has it.

    bundles_root: e.g. F:/overmind/data/nightly_reports/bundles/
    Sub-directory structure: <YYYY-MM-DD>/<project_id>.json
    """
    if not bundles_root.is_dir():
        return None
    earliest: datetime | None = None
    for date_dir in sorted(bundles_root.iterdir()):
        if not date_dir.is_dir():
            continue
        # Date-dir names are YYYY-MM-DD; parse the dir name not the file mtime
        try:
            dt = datetime.strptime(date_dir.name, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        bundle_path = date_dir / f"{project_name}.json"
        if not bundle_path.is_file():
            continue
        try:
            data = json.loads(bundle_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("verdict") == "UNVERIFIED":
            if earliest is None or dt < earliest:
                earliest = dt
        else:
            # Bundle exists but verdict is NOT UNVERIFIED — reset.
            # A project that flipped CERTIFIED then back to UNVERIFIED should
            # count its age from the most recent transition into UNVERIFIED,
            # not from the original one. Earliest is reset by setting to None.
            earliest = None
    return earliest


def escalate(
    unverified_rows: Iterable[dict],
    bundles_root: Path,
    policy: UnverifiedPolicy | None = None,
    now: datetime | None = None,
) -> list[EscalatedProject]:
    """Return the subset of unverified projects that exceed the age threshold.

    unverified_rows is the same list rendered into the markdown UNVERIFIED
    section by scripts/nightly_verify.py (each row has 'project' and 'bundle').
    """
    if policy is None:
        policy = UnverifiedPolicy.from_env()
    if now is None:
        now = datetime.now(timezone.utc)

    out: list[EscalatedProject] = []
    for r in unverified_rows:
        name = r["project"].name if hasattr(r["project"], "name") else str(r["project"])
        first = find_first_unverified_date(name, bundles_root)
        if first is None:
            # No historical bundle — this is the project's first UNVERIFIED.
            # Don't escalate; the age clock starts today.
            continue
        days = (now - first).days
        if days >= policy.age_threshold_days:
            reason = ""
            try:
                reason = r["bundle"].arbitration_reason or ""
            except (AttributeError, KeyError):
                pass
            out.append(EscalatedProject(
                project_name=name,
                first_unverified_at=first,
                days_unverified=days,
                arbitration_reason=reason,
            ))
    out.sort(key=lambda e: e.days_unverified, reverse=True)
    return out


def render_escalations_md(
    escalated: list[EscalatedProject],
    policy: UnverifiedPolicy,
) -> list[str]:
    """Markdown lines for insertion into the nightly report just after the
    UNVERIFIED table. Returns an empty list if nothing to escalate."""
    if not escalated:
        return []
    lines = [
        "### Escalations: UNVERIFIED ≥ %d days" % policy.age_threshold_days,
        "",
        "_These projects have been UNVERIFIED for longer than the operator-configured"
        " threshold (`OVERMIND_UNVERIFIED_AGE_DAYS`). Most likely cause: the numerical"
        " baseline was never created. Owner action required._",
        "",
        "| Project | Days UNVERIFIED | First seen | Reason |",
        "|---------|-----------------|-----------|--------|",
    ]
    for e in escalated:
        lines.append(
            f"| {e.project_name} | {e.days_unverified} | "
            f"{e.first_unverified_at.date().isoformat()} | "
            f"{e.arbitration_reason[:80]} |"
        )
    lines.append("")
    return lines


def should_attention_prefix(unverified_count: int, policy: UnverifiedPolicy) -> bool:
    """Return True if the nightly report header should get an [ATTENTION] prefix."""
    return unverified_count > policy.count_threshold
