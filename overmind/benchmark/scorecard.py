"""Render benchmark metrics + win condition into a JSON + Markdown scorecard (§3)."""
from __future__ import annotations

import json
from pathlib import Path


def _fmt(x) -> str:
    return "n/a" if x is None else (f"{x:.4f}" if isinstance(x, float) else str(x))


def render_markdown(scorecard: dict) -> str:
    lines = ["# Benchmark scorecard", "", f"Slice: {scorecard.get('slice','?')}  ",
             f"Held-out tasks: {scorecard.get('held_out_n','?')}  ",
             f"Generated: {scorecard.get('generated_at','(stamp on write)')}", "",
             "| arm | status | caught-defect | false-alarm | parity | agreement | accepted | cost/accepted | blended |",
             "|---|---|---|---|---|---|---|---|---|"]
    for arm in scorecard.get("arms", []):
        m = arm.get("metrics") or {}
        lines.append(
            f"| {arm['arm']} | {arm['status']} | {_fmt(m.get('caught_defect_rate'))} | "
            f"{_fmt(m.get('false_alarm_rate'))} | {_fmt(m.get('parity_rate'))} | "
            f"{_fmt(m.get('agreement_soundness'))} | {m.get('accepted','-')} | "
            f"{_fmt(m.get('cost_per_accepted_change'))} | {_fmt(m.get('blended'))} |"
        )
    wc = scorecard.get("win_condition")
    lines += ["", "## Win condition"]
    if wc:
        lines.append(f"**Verdict: {wc['verdict']}** (C>A={wc['c_beats_a']}, C>B={wc['c_beats_b']}, affordable={wc['affordable']})")
        for n in wc.get("notes", []):
            lines.append(f"- {n}")
    else:
        lines.append("_Pending: needs Arms A, B, C all run (model capacity)._")
    wcg = scorecard.get("win_condition_conformal")
    if wcg:
        lines += ["", "### With conformal accept/abstain gate (PV-B)",
                  f"**Verdict: {wcg['verdict']}** (C>A={wcg['c_beats_a']}, C>B={wcg['c_beats_b']}, "
                  f"affordable={wcg['affordable']})"]
        for n in wcg.get("notes", []):
            lines.append(f"- {n}")
    if scorecard.get("notes"):
        lines += ["", "## Notes"]
        lines += [f"- {n}" for n in scorecard["notes"]]
    return "\n".join(lines) + "\n"


def write_scorecard(out_dir: Path | str, scorecard: dict) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "scorecard.json").write_text(json.dumps(scorecard, indent=1), encoding="utf-8")
    (out / "scorecard.md").write_text(render_markdown(scorecard), encoding="utf-8")
    return {"json": str(out / "scorecard.json"), "md": str(out / "scorecard.md")}
