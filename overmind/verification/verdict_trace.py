"""Span-level tracing for the verdict pipeline (audit / observability gap).

The stack had good *aggregate* metrics and excellent *audit* artifacts (signed
bundles, JSONL finding streams) but **no span-level trace** — you could not open
one verdict and watch its witness→judge→arbitrator path with per-stage
token/latency spans. This module is that primitive: a tiny, dependency-free
tracer (no OpenTelemetry dependency, but OTel-shaped: spans with ids, parents,
timing, and attributes) that the verdict pipeline can emit into.

Design notes:
  * Deterministic STRUCTURE (span ids are sequential, parents are explicit) so a
    trace's shape is reproducible run-to-run; only the wall-clock latency fields
    vary (like a log timestamp) — those are never used as scored eval fields.
  * Zero behavior change when no tracer is passed (callers default ``tracer=None``).
  * ``span_coverage`` lets an eval assert every expected pipeline stage emitted a
    span (the before→after observability number).
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator


@dataclass(slots=True)
class TraceSpan:
    span_id: int
    name: str
    parent_id: int | None
    start_ns: int
    end_ns: int | None = None
    tokens: int | None = None
    status: str = "ok"
    attributes: dict[str, object] = field(default_factory=dict)

    @property
    def latency_ms(self) -> float | None:
        if self.end_ns is None:
            return None
        return round((self.end_ns - self.start_ns) / 1_000_000, 3)


class VerdictTracer:
    """Collects a tree of spans for one verdict's pipeline.

    Usage::

        tracer = VerdictTracer()
        with tracer.span("witness:test_suite", tokens=0):
            ...
        with tracer.span("judge", tokens=1200):
            with tracer.span("arbitrator"):
                ...
    """

    def __init__(self) -> None:
        self._spans: list[TraceSpan] = []
        self._stack: list[int] = []
        self._next_id = 0

    @contextmanager
    def span(self, name: str, *, tokens: int | None = None, **attributes) -> Iterator[TraceSpan]:
        span = TraceSpan(
            span_id=self._next_id,
            name=name,
            parent_id=self._stack[-1] if self._stack else None,
            start_ns=time.perf_counter_ns(),
            tokens=tokens,
            attributes=dict(attributes),
        )
        self._next_id += 1
        self._spans.append(span)
        self._stack.append(span.span_id)
        try:
            yield span
        except Exception as exc:  # noqa: BLE001 — record failure, re-raise
            span.status = f"error:{type(exc).__name__}"
            raise
        finally:
            span.end_ns = time.perf_counter_ns()
            self._stack.pop()

    @property
    def spans(self) -> list[TraceSpan]:
        return list(self._spans)

    def span_names(self) -> list[str]:
        return [s.name for s in self._spans]

    def total_tokens(self) -> int:
        return sum(s.tokens or 0 for s in self._spans)

    def is_tree_consistent(self) -> bool:
        """Every non-root span points at a real, already-opened parent and every
        span was closed (end_ns set)."""
        ids = {s.span_id for s in self._spans}
        for s in self._spans:
            if s.end_ns is None:
                return False
            if s.parent_id is not None and s.parent_id not in ids:
                return False
        return True

    def span_coverage(self, expected_stages: list[str]) -> float:
        """Fraction of ``expected_stages`` that have at least one span whose name
        starts with that stage prefix (e.g. 'witness' matches 'witness:smoke')."""
        if not expected_stages:
            return 0.0
        names = self.span_names()
        covered = sum(1 for stage in expected_stages
                      if any(n == stage or n.startswith(stage + ":") for n in names))
        return round(covered / len(expected_stages), 4)

    def to_dict(self) -> dict:
        return {
            "spans": [
                {
                    "span_id": s.span_id,
                    "name": s.name,
                    "parent_id": s.parent_id,
                    "tokens": s.tokens,
                    "status": s.status,
                    "latency_ms": s.latency_ms,
                    "attributes": s.attributes,
                }
                for s in self._spans
            ],
            "total_tokens": self.total_tokens(),
            "tree_consistent": self.is_tree_consistent(),
        }
