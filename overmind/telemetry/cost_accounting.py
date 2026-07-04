"""Cost-per-accepted-change instrument (T12b / WORLD_CLASS_SPEC D5).

The stack measured *verdicts* and *eval deltas* but never **loop economics**:
tokens/dollars per accepted change, and the acceptance rate. Without that, a
truth-gated harness can quietly cost 10x a single agent for the same accepted
output and nobody sees it until the invoice. This module is the instrument.

It reads **real spend** where the vendor reports it — `claude -p --output-format
json` emits a ``total_cost_usd`` field — and falls back to a clearly-labelled
token×price *estimate* for engines that only report usage (Codex/agy). It then
accumulates cost events against accepted/rejected change events and computes:

  * cost-per-accepted-change  (total USD / #accepted)
  * acceptance rate           (#accepted / #decisions)
  * below-break-even flag      (acceptance < BREAK_EVEN — a *heuristic*, not a
                                measured constant; see the research doc §1.5
                                truth-first note. Labelled as such everywhere.)

Pure data + parsing; no third-party dependency; no hot-path coupling. A loop can
opt in by constructing a ``CostLedger`` and feeding it events. Optional
append-only JSONL persistence for cross-session aggregation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# Practitioner break-even heuristic (loop is net-negative below ~50% acceptance).
# NOT a measured constant — a design signal only (research doc §1.5).
BREAK_EVEN_ACCEPTANCE = 0.50

# Rough per-1M-token USD price anchors for token→cost ESTIMATES only (used when a
# vendor reports usage but not dollars). Deliberately conservative & labelled as
# estimates; real dollars always come from total_cost_usd when present.
_DEFAULT_PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    # engine -> (input $/Mtok, output $/Mtok)
    "claude": (3.0, 15.0),
    "codex": (2.5, 10.0),
    "agy": (1.25, 5.0),
    "gemini": (1.25, 5.0),
    "local": (0.0, 0.0),
    "unknown": (2.0, 10.0),
}


@dataclass(slots=True)
class CostEvent:
    """One metered unit of spend attributed to a loop/engine."""

    loop: str
    engine: str
    usd: float                      # dollars (real if measured, else estimated)
    measured: bool                  # True = from vendor total_cost_usd; False = token estimate
    input_tokens: int = 0
    output_tokens: int = 0
    label: str = ""                 # free-text (task id, stage, …)

    def to_dict(self) -> dict:
        return {
            "loop": self.loop,
            "engine": self.engine,
            "usd": round(self.usd, 6),
            "measured": self.measured,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "label": self.label,
        }


def estimate_usd(engine: str, input_tokens: int, output_tokens: int,
                 price_table: dict[str, tuple[float, float]] | None = None) -> float:
    """Token→USD estimate for engines that don't report dollars. LABELLED as an
    estimate by the caller (CostEvent.measured=False)."""
    table = price_table or _DEFAULT_PRICE_PER_MTOK
    pin, pout = table.get(engine.strip().lower(), table["unknown"])
    return (max(0, input_tokens) / 1_000_000.0) * pin + (max(0, output_tokens) / 1_000_000.0) * pout


def parse_claude_json_cost(raw: str, *, loop: str = "", label: str = "") -> CostEvent | None:
    """Parse the JSON emitted by ``claude -p --output-format json`` into a
    *measured* CostEvent.

    The headless result object carries ``total_cost_usd`` and a ``usage`` block
    (``input_tokens`` / ``output_tokens``, sometimes with cache token fields).
    Tolerant of extra/missing fields and of a stream where the JSON is the last
    non-empty line. Returns ``None`` if no cost object can be parsed (caller
    then falls back to a token estimate).
    """
    obj = _extract_json_object(raw)
    if obj is None:
        return None
    if "total_cost_usd" not in obj and "cost_usd" not in obj:
        return None
    usd = obj.get("total_cost_usd", obj.get("cost_usd"))
    try:
        usd = float(usd)
    except (TypeError, ValueError):
        return None
    usage = obj.get("usage") or {}
    in_tok = _int(usage.get("input_tokens"))
    out_tok = _int(usage.get("output_tokens"))
    return CostEvent(
        loop=loop,
        engine="claude",
        usd=usd,
        measured=True,
        input_tokens=in_tok,
        output_tokens=out_tok,
        label=label,
    )


def _extract_json_object(raw: str) -> dict | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    # Fast path: whole thing is JSON.
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    # Otherwise scan lines bottom-up for the last JSON object (result line).
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                continue
    return None


def _int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


@dataclass(slots=True)
class LoopEconomics:
    """Computed economics for one loop (or the whole ledger)."""

    loop: str
    total_usd: float
    measured_usd: float
    estimated_usd: float
    accepted: int
    rejected: int
    cost_events: int

    @property
    def decisions(self) -> int:
        return self.accepted + self.rejected

    @property
    def acceptance_rate(self) -> float | None:
        return (self.accepted / self.decisions) if self.decisions else None

    @property
    def cost_per_accepted_change(self) -> float | None:
        return (self.total_usd / self.accepted) if self.accepted else None

    @property
    def below_break_even(self) -> bool | None:
        """True when acceptance < BREAK_EVEN_ACCEPTANCE. HEURISTIC signal only —
        not a measured threshold. ``None`` when there are no decisions yet."""
        rate = self.acceptance_rate
        return None if rate is None else rate < BREAK_EVEN_ACCEPTANCE

    def to_dict(self) -> dict:
        cpac = self.cost_per_accepted_change
        rate = self.acceptance_rate
        return {
            "loop": self.loop,
            "total_usd": round(self.total_usd, 6),
            "measured_usd": round(self.measured_usd, 6),
            "estimated_usd": round(self.estimated_usd, 6),
            "accepted": self.accepted,
            "rejected": self.rejected,
            "decisions": self.decisions,
            "acceptance_rate": None if rate is None else round(rate, 4),
            "cost_per_accepted_change_usd": None if cpac is None else round(cpac, 6),
            "below_break_even_heuristic": self.below_break_even,
            "cost_events": self.cost_events,
        }


class CostLedger:
    """Accumulates cost + accept/reject events and computes loop economics.

    Not thread-safe by design (one ledger per loop run); callers that need
    durability pass ``jsonl_path`` to append every event for cross-session roll-up.
    """

    def __init__(self, jsonl_path: Path | str | None = None) -> None:
        self._events: list[CostEvent] = []
        self._accepted: dict[str, int] = {}
        self._rejected: dict[str, int] = {}
        self._jsonl_path = Path(jsonl_path) if jsonl_path else None

    # --- ingest ---------------------------------------------------------------
    def add_cost(self, event: CostEvent) -> None:
        self._events.append(event)
        self._append_jsonl({"kind": "cost", **event.to_dict()})

    def add_claude_json(self, raw: str, *, loop: str = "", label: str = "",
                        fallback_engine: str = "claude") -> CostEvent:
        """Convenience: parse a `claude -p --output-format json` blob and record
        it. Falls back to a zero-dollar estimate event if unparseable, so the
        ledger still counts the call (marked measured=False)."""
        event = parse_claude_json_cost(raw, loop=loop, label=label)
        if event is None:
            event = CostEvent(loop=loop, engine=fallback_engine, usd=0.0,
                              measured=False, label=label or "unparsed_cost")
        else:
            event.loop = loop or event.loop
        self.add_cost(event)
        return event

    def add_usage_estimate(self, engine: str, input_tokens: int, output_tokens: int,
                           *, loop: str = "", label: str = "") -> CostEvent:
        """Record a token→USD *estimate* for an engine that only reports usage."""
        usd = estimate_usd(engine, input_tokens, output_tokens)
        event = CostEvent(loop=loop, engine=engine, usd=usd, measured=False,
                          input_tokens=input_tokens, output_tokens=output_tokens, label=label)
        self.add_cost(event)
        return event

    def record_decision(self, accepted: bool, *, loop: str = "") -> None:
        """Record an accepted or rejected change for a loop."""
        bucket = self._accepted if accepted else self._rejected
        bucket[loop] = bucket.get(loop, 0) + 1
        self._append_jsonl({"kind": "decision", "loop": loop, "accepted": accepted})

    # --- read-out -------------------------------------------------------------
    def economics(self, loop: str | None = None) -> LoopEconomics:
        """Economics for one loop, or the whole ledger when ``loop`` is None."""
        events = self._events if loop is None else [e for e in self._events if e.loop == loop]
        total = sum(e.usd for e in events)
        measured = sum(e.usd for e in events if e.measured)
        estimated = sum(e.usd for e in events if not e.measured)
        if loop is None:
            accepted = sum(self._accepted.values())
            rejected = sum(self._rejected.values())
        else:
            accepted = self._accepted.get(loop, 0)
            rejected = self._rejected.get(loop, 0)
        return LoopEconomics(
            loop=loop or "*",
            total_usd=total,
            measured_usd=measured,
            estimated_usd=estimated,
            accepted=accepted,
            rejected=rejected,
            cost_events=len(events),
        )

    def loops(self) -> list[str]:
        names = {e.loop for e in self._events} | set(self._accepted) | set(self._rejected)
        return sorted(n for n in names if n)

    def report(self) -> dict:
        """Full report: overall + per-loop economics, ready to serialise."""
        return {
            "overall": self.economics().to_dict(),
            "loops": {name: self.economics(name).to_dict() for name in self.loops()},
        }

    def _append_jsonl(self, record: dict) -> None:
        if self._jsonl_path is None:
            return
        try:
            self._jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            with self._jsonl_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\n")
        except OSError:
            # persistence is best-effort; never break a loop over a log write
            pass


def aggregate_events(events: Iterable[CostEvent]) -> LoopEconomics:
    """Fold a bare iterable of cost events into overall economics (no decisions).
    Handy for post-hoc roll-ups from a JSONL stream."""
    ledger = CostLedger()
    for e in events:
        ledger.add_cost(e)
    return ledger.economics()
