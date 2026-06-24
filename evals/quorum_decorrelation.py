"""Eval 4 — quorum decorrelation enforcement (audit A2 hard-enforcement).

Measures whether the cross-engine quorum, when asked to run a *correlated* panel
(two judges from the same model family), still executes as a multi-engine quorum
that **overstates its independence** — or whether hard enforcement repairs/rejects
it so every surviving quorum is genuinely different-family.

Background: *Nine Judges, Two Effective Votes* (arXiv:2605.29800) — same-family
judges share correlated failure modes, so a "3-engine" panel spanning 2 families
is ~2.25 effective votes, not 3. The prior behavior was **warn-only** (the panel
ran, just flagged). This eval quantifies the move from warn-only → hard-enforced.

Headline metric — **overcounting quorum rate**: of the correlated panels
(distinct_families < nominal engines), the fraction that still *run as a
QuorumJudge whose effective_votes < nominal_votes* (i.e. advertise more
independence than they have).

  before (enforce OFF) → after (enforce ON)

Run against the REAL ``overmind.verification.judge_factory.build_judge`` so this
proves the wiring, not just the helper. Construction never queries a backend.
"""
from __future__ import annotations

from dataclasses import dataclass

from overmind.verification.judge_factory import (
    build_judge,
    estimate_effective_votes,
    family_for_engine,
)
from overmind.verification.llm_judge import QuorumJudge

from evals.common import pct, write_result


@dataclass(frozen=True)
class PanelCase:
    name: str
    spec: str             # comma-separated engine spec
    correlated: bool      # distinct families < nominal engines


# A spread of panels: correlated (same family appears twice) and honest
# (all-distinct). Engines are real names from ENGINE_FAMILY.
_PANELS: list[PanelCase] = [
    # ── correlated panels (overcount independence if run as-is) ──
    PanelCase("two_openai_seats", "codex,codex-noreen", correlated=True),
    PanelCase("two_google", "agy,gemini", correlated=True),
    PanelCase("claude_plus_two_openai", "claude,codex,codex-noreen", correlated=True),
    PanelCase("claude_x2", "claude,claude", correlated=True),
    PanelCase("google_x2_plus_openai", "agy,gemini,codex", correlated=True),
    # ── honest panels (all distinct families; enforcement must NOT change) ──
    PanelCase("anthropic_openai", "claude,codex", correlated=False),
    PanelCase("three_families", "claude,codex,gemini", correlated=False),
    PanelCase("anthropic_google", "claude,gemini", correlated=False),
]


def _panel_profile(spec: str, enforce: bool) -> dict:
    """Build the real judge for ``spec`` and report its independence profile."""
    judge = build_judge(spec=spec, mode="quorum", enforce_families=enforce)
    if isinstance(judge, QuorumJudge):
        return {
            "kind": "quorum",
            "n_judges": len(judge.judges),
            "nominal_votes": judge.nominal_votes,
            "effective_votes": judge.effective_votes,
            "distinct_families": judge.distinct_families,
            # overcounts independence iff it runs as a quorum with fewer
            # effective than nominal votes (same-family redundancy survived).
            "overcounts": judge.effective_votes < judge.nominal_votes,
        }
    # Fell back to a single-engine chain: not a quorum, advertises no panel
    # independence at all -> cannot overcount.
    return {"kind": "fallback", "overcounts": False}


def evaluate() -> dict:
    rows = []
    for case in _PANELS:
        engines = [e.strip() for e in case.spec.split(",")]
        ev = estimate_effective_votes(engines)
        before = _panel_profile(case.spec, enforce=False)
        after = _panel_profile(case.spec, enforce=True)
        rows.append({
            "name": case.name,
            "spec": case.spec,
            "correlated": case.correlated,
            "distinct_families": ev.distinct_families,
            "nominal": ev.nominal,
            "before": before,
            "after": after,
            # honest panels must be untouched by enforcement (no-regression):
            "honest_panel_unchanged": (
                (not case.correlated)
                and before.get("kind") == "quorum"
                and after.get("kind") == "quorum"
                and after["n_judges"] == before["n_judges"]
            ),
        })

    correlated = [r for r in rows if r["correlated"]]
    honest = [r for r in rows if not r["correlated"]]

    overcount_before = sum(1 for r in correlated if r["before"]["overcounts"])
    overcount_after = sum(1 for r in correlated if r["after"]["overcounts"])

    honest_unchanged = sum(1 for r in honest if r["honest_panel_unchanged"])

    payload = {
        "eval": "quorum_decorrelation",
        "n_panels": len(rows),
        "correlated_panels": {
            "n": len(correlated),
            "overcount_before": overcount_before,
            "overcount_rate_before": pct(overcount_before, len(correlated)),
            "overcount_after": overcount_after,
            "overcount_rate_after": pct(overcount_after, len(correlated)),
        },
        "honest_panels": {
            "n": len(honest),
            "unchanged": honest_unchanged,
            "unchanged_rate": pct(honest_unchanged, len(honest)),
        },
        "panels": rows,
    }
    return payload


def main() -> dict:
    payload = evaluate()
    c = payload["correlated_panels"]
    h = payload["honest_panels"]
    path = write_result("quorum_decorrelation", payload)
    print(f"[quorum_decorrelation] correlated-panel overcount rate: "
          f"{c['overcount_rate_before']:.0%} (before) -> {c['overcount_rate_after']:.0%} (after) "
          f"[{c['overcount_before']}/{c['n']} -> {c['overcount_after']}/{c['n']}]")
    print(f"[quorum_decorrelation] honest panels unchanged: "
          f"{h['unchanged']}/{h['n']} ({h['unchanged_rate']:.0%}) -- no-regression check")
    print(f"[quorum_decorrelation] -> {path}")
    return payload


if __name__ == "__main__":
    main()
