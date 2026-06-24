"""Parallel verification-job dispatch across registered nodes."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable

from overmind.cluster.registry import NodeRegistry


@dataclass(slots=True)
class DispatchResult:
    results: list[dict] = field(default_factory=list)
    dispatched: int = 0
    skipped: int = 0
    errors: list[dict] = field(default_factory=list)


class Dispatcher:
    """Fans verification jobs out across a registry's executors.

    Uses a thread pool sized to the registry's total local parallelism (witness
    jobs are subprocess/IO-bound, so threads give real concurrency despite the
    GIL). Deterministic OUTPUT ordering: results are returned sorted by repo so a
    run is reproducible regardless of completion order.
    """

    def __init__(self, registry: NodeRegistry) -> None:
        self.registry = registry

    def dispatch(
        self,
        jobs: list[dict],
        runner: Callable[[dict], dict],
        *,
        node_name: str | None = None,
    ) -> DispatchResult:
        if not jobs:
            return DispatchResult()
        # Pick a local executor (remote transport is deferred). Round-robin across
        # local nodes would go here once there are several; today we use one.
        local_nodes = self.registry.local_nodes()
        if not local_nodes:
            raise RuntimeError("no local nodes registered; register_local() first")
        target = node_name or local_nodes[0].name
        executor = self.registry.executor_for(target)
        max_workers = max(1, self.registry.total_parallelism(local_only=True))

        out = DispatchResult(dispatched=len(jobs))
        results: list[dict] = []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futs = {pool.submit(executor.run, job, runner): job for job in jobs}
            for fut in as_completed(futs):
                job = futs[fut]
                try:
                    results.append(fut.result())
                except Exception as exc:  # noqa: BLE001 — isolate per-job failure
                    out.errors.append({"repo": job.get("repo"), "error": f"{type(exc).__name__}: {exc}"})
        out.results = sorted(results, key=lambda r: str(r.get("repo")))
        return out
