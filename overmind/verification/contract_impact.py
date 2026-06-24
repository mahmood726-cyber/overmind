"""Cross-repo contract-impact verification (audit B1).

Overmind verifies each project independently — it does not detect when a change
to a *shared* module / schema / fixture breaks a **dependent** project's
contract. The 2026 industry pattern (Qodo / CodeRabbit linked-repos, Greptile
code graph) is: register consumer repos, and on a shared-dependency change, fan
out to the dependents' witnesses.

This module is the fan-out core. It reuses the same transitive-closure primitive
as the memory retraction graph (`ClaimGraph`) — a dependent's relationship to a
shared module is exactly "depends_on" — so a change to a shared module selects
the transitive closure of impacted repos. The critical safety property (house
lesson, and the C5 delta-skip caveat): **never skip a repo whose upstream
dependency changed** — so the impact set must include *every* transitive
dependent, which a closure guarantees.

Honest scope: this computes the impact SET from an explicit dependency map; it
does not auto-discover the map (that needs an import/schema scanner across the
portfolio — a follow-up). Given the map, the fan-out is exact.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from overmind.verification.claim_graph import ClaimGraph


@dataclass(slots=True)
class ImpactResult:
    changed: list[str]                       # shared modules/repos that changed
    impacted_repos: list[str] = field(default_factory=list)  # transitive dependents to re-verify
    unknown_changed: list[str] = field(default_factory=list)  # changed ids not in the map


class ContractImpactGraph:
    """A portfolio dependency map: repo --depends_on--> shared module / other repo.

    ``add_dependency(repo, depends_on=module)`` records that ``repo`` consumes
    ``module``. ``impacted_by(*changed)`` returns the transitive closure of repos
    that must re-run their witnesses when ``changed`` is modified.
    """

    def __init__(self) -> None:
        self._graph = ClaimGraph()
        self._repos: set[str] = set()

    def add_repo(self, repo: str) -> None:
        self._repos.add(repo)
        self._graph.add_node(repo)

    def add_dependency(self, repo: str, depends_on: str) -> None:
        """``repo`` depends on the shared module/repo ``depends_on``."""
        self._repos.add(repo)
        self._graph.add_dependency(repo, depends_on=depends_on)

    @property
    def repos(self) -> set[str]:
        return set(self._repos)

    def impacted_by(self, *changed: str) -> ImpactResult:
        """Repos whose witnesses must re-run because ``changed`` was modified.

        Returns the transitive closure of dependents (NOT the changed nodes
        themselves unless they are also repos that depend on a changed node).
        A changed shared module with no dependents impacts nothing.
        """
        result = self._graph.retract(*changed)
        # Dependents of the changed nodes = the impact set. Restrict to known repos
        # (a changed module that is not itself a repo should not appear).
        impacted = [n for n in result.invalidated if n in self._repos]
        # A changed node that is itself a repo is also impacted (it changed).
        for c in result.retracted:
            if c in self._repos and c not in impacted:
                impacted.append(c)
        return ImpactResult(
            changed=list(changed),
            impacted_repos=impacted,
            unknown_changed=result.unknown_seeds,
        )

    def naive_impacted_by(self, *changed: str) -> list[str]:
        """Baseline: the *direct* consumers only (one hop) — what a non-graph,
        per-repo verifier that ignores transitive impact would catch. Misses
        dependents-of-dependents."""
        direct = []
        for c in changed:
            for dep in self._graph.dependents(c):
                if dep in self._repos and dep not in direct:
                    direct.append(dep)
        return direct
