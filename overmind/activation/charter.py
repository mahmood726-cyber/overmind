"""Loop Charter: instantiate LOOP_CHARTER_TEMPLATE.md for a given run.

QW-5 from FRONTIER-AGENT-SCAN-2026-06.md (ADDITIVE — new module + CLI command;
no existing code paths changed).

Usage via CLI:
    overmind charter init
    overmind charter init --goal "all tier-3 projects CERTIFIED" --budget-usd 2.0
"""
from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path


_TEMPLATE_PATH = Path(__file__).parent / "LOOP_CHARTER_TEMPLATE.md"


def init_charter(
    data_dir: Path,
    date: str | None = None,
    goal: str = "all high-risk projects CERTIFIED or circuit-open",
    project_count: int = 0,
    paths_filter: str = "(none)",
    min_risk: str = "medium",
    limit: int = 50,
    budget_usd: float | None = None,
    circuit_threshold: int = 5,
) -> Path:
    """Instantiate the charter template and write to data/charter_{date}.md.

    Returns the path of the written charter file.
    """
    if date is None:
        date = datetime.now(UTC).strftime("%Y-%m-%d")

    template = _TEMPLATE_PATH.read_text(encoding="utf-8")

    budget_str = f"{budget_usd:.2f}" if budget_usd is not None else "(not set — LLM phase uncapped)"
    charter = (
        template
        .replace("{date}", date)
        .replace("{goal}", goal)
        .replace("{project_count}", str(project_count))
        .replace("{paths_filter}", str(paths_filter))
        .replace("{min_risk}", min_risk)
        .replace("{limit}", str(limit))
        .replace("{budget_usd}", budget_str)
        .replace("{circuit_threshold}", str(circuit_threshold))
    )

    data_dir.mkdir(parents=True, exist_ok=True)
    out_path = data_dir / f"charter_{date}.md"
    out_path.write_text(charter, encoding="utf-8")
    return out_path
