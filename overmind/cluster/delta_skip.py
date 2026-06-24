"""Delta-skip hash-gate: verify only what changed, safely.

Skips a repo whose content hash matches its last green verdict — EXCEPT when a
cross-repo dependency changed, in which case the repo must re-verify even though
its own content is unchanged. That exception is the whole safety point (house
lesson + C5 caveat: never skip a project whose upstream dependency changed), and
it is enforced by routing the changed set through the #3d ContractImpactGraph.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from overmind.verification.contract_impact import ContractImpactGraph


@dataclass(slots=True)
class SkipDecision:
    to_run: list[str] = field(default_factory=list)        # repos that will verify
    skipped: list[str] = field(default_factory=list)       # repos skipped (unchanged + no dep change)
    changed_directly: list[str] = field(default_factory=list)
    pulled_in_by_impact: list[str] = field(default_factory=list)  # unchanged but a dep changed


class DeltaSkipGate:
    """Decide which repos to (re)verify given content hashes + a dependency map.

    ``last_hashes``: repo -> hash at last green verdict.
    ``current_hashes``: repo -> current content hash.
    ``impact_graph``: optional ContractImpactGraph; if a changed repo/module has
    dependents, those dependents are pulled in even if their own hash is unchanged.
    """

    def __init__(self, impact_graph: ContractImpactGraph | None = None) -> None:
        self.impact_graph = impact_graph

    def decide(
        self,
        last_hashes: dict[str, str],
        current_hashes: dict[str, str],
    ) -> SkipDecision:
        # Hashed nodes can include shared MODULES (change-sources) as well as
        # repos. Only repos are ever "run" or "skipped"; a module change just
        # triggers impact. When an impact graph is supplied, its declared repos
        # define the repo set; otherwise every hashed key is treated as a repo.
        all_nodes = sorted(current_hashes)
        changed = [n for n in all_nodes if last_hashes.get(n) != current_hashes[n]]

        if self.impact_graph is not None:
            repo_set = self.impact_graph.repos
            impacted: set[str] = set()
            if changed:
                res = self.impact_graph.impacted_by(*changed)
                impacted = {r for r in res.impacted_repos if r in repo_set}
        else:
            repo_set = set(all_nodes)
            impacted = set()

        repos = sorted(repo_set)
        changed_repos = [r for r in changed if r in repo_set]
        must_run = set(changed_repos) | impacted
        pulled_in = sorted(impacted - set(changed_repos))

        to_run = [r for r in repos if r in must_run]
        skipped = [r for r in repos if r not in must_run]
        return SkipDecision(
            to_run=to_run,
            skipped=skipped,
            changed_directly=sorted(changed),
            pulled_in_by_impact=pulled_in,
        )
