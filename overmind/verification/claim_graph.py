"""Claim→evidence dependency graph with retraction propagation (audit B2).

Today's freshness model is *flat*: ``MemoryStore.is_stale`` recomputes a source
hash and invalidates the one memory whose source changed. But a conclusion built
*on top of* that memory is not touched — so a retracted premise can leave its
downstream conclusions standing. *Grounded Continuation*
(arXiv:2605.14175) formalizes the fix: model claims and evidence as a directed
dependency graph and, when a node is retracted, **propagate the retraction to the
transitive closure of everything that depended on it**.

This module is the pure, deterministic algorithm — no I/O, no DB — so it is
trivially testable and reusable by both the memory layer (premise staleness ⇒
invalidate dependents) and the verdict layer (a witness retraction ⇒ invalidate
the claims it supported).

Edge direction convention: ``add_dependency(claim, depends_on=evidence)`` means
"``claim`` depends on ``evidence``". Retracting ``evidence`` invalidates
``claim`` and anything that, in turn, depended on ``claim``.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class RetractionResult:
    """Outcome of retracting one or more nodes."""
    retracted: list[str]              # the directly-retracted seed nodes (that exist)
    invalidated: list[str]            # downstream dependents invalidated (deterministic order)
    unknown_seeds: list[str] = field(default_factory=list)  # seeds not in the graph

    @property
    def all_affected(self) -> list[str]:
        """Seeds + downstream, deduplicated, retracted-first then invalidated."""
        seen: set[str] = set()
        out: list[str] = []
        for n in self.retracted + self.invalidated:
            if n not in seen:
                seen.add(n)
                out.append(n)
        return out


class ClaimGraph:
    """A directed dependency graph of claims and the evidence they rest on.

    Cycle-safe (a visited set bounds traversal) and deterministic (dependents are
    visited in insertion order), so the same retraction always yields the same
    closure — a house requirement for reproducible verdicts.
    """

    def __init__(self) -> None:
        # node -> list of nodes it DEPENDS ON (claim -> [evidence...])
        self._depends_on: dict[str, list[str]] = {}
        # reverse index: node -> list of nodes that depend ON it (evidence -> [claim...])
        self._dependents: dict[str, list[str]] = {}

    def add_node(self, node: str) -> None:
        self._depends_on.setdefault(node, [])
        self._dependents.setdefault(node, [])

    def add_dependency(self, claim: str, depends_on: str) -> None:
        """Record that ``claim`` depends on the ``depends_on`` evidence/premise."""
        if claim == depends_on:
            raise ValueError(f"a claim cannot depend on itself: {claim!r}")
        self.add_node(claim)
        self.add_node(depends_on)
        if depends_on not in self._depends_on[claim]:
            self._depends_on[claim].append(depends_on)
        if claim not in self._dependents[depends_on]:
            self._dependents[depends_on].append(claim)

    def depends_on(self, node: str) -> list[str]:
        return list(self._depends_on.get(node, []))

    def dependents(self, node: str) -> list[str]:
        return list(self._dependents.get(node, []))

    @property
    def nodes(self) -> list[str]:
        return list(self._depends_on.keys())

    def retract(self, *seeds: str) -> RetractionResult:
        """Retract ``seeds`` and propagate to the transitive closure of dependents.

        Returns the seeds that existed (``retracted``), the downstream dependents
        invalidated (``invalidated``, deterministic order, excluding the seeds),
        and any seeds not in the graph (``unknown_seeds``). A seed with no
        dependents invalidates nothing — exactly the no-over-propagation property
        the eval checks.
        """
        retracted: list[str] = []
        unknown: list[str] = []
        for s in seeds:
            if s in self._depends_on:
                retracted.append(s)
            else:
                unknown.append(s)

        seed_set = set(retracted)
        invalidated: list[str] = []
        seen: set[str] = set(retracted)
        # BFS over the reverse (dependents) edges, insertion-ordered.
        frontier = list(retracted)
        while frontier:
            node = frontier.pop(0)
            for dep in self._dependents.get(node, []):
                if dep not in seen:
                    seen.add(dep)
                    if dep not in seed_set:
                        invalidated.append(dep)
                    frontier.append(dep)
        return RetractionResult(
            retracted=retracted, invalidated=invalidated, unknown_seeds=unknown,
        )
