"""Job scheduler: capability-aware, load-balancing, requeue-safe dispatch.

Routes each verification job to a node by, in order:

  1. **Capability match** — the node must have every engine the job declares
     (``needs_engines``) AND every data volume it needs (``needs_data``). The
     data-volume check *is* data-locality: a job that needs ``E:\\AACT`` only goes
     to a node that actually has that volume, so we never ship a job to a node
     lacking its data.
  2. **Current load** — among capable, online nodes with free capacity, pick the
     least-loaded (fewest in-flight jobs relative to its cap, then observed load).
  3. **Concurrency cap** — a node never runs more than ``max_parallel`` jobs at
     once, so dispatch can't re-create today's single-box saturation.

Safety: a node that fails mid-job with a connection-level error
(``RemoteTransientError``) is marked **offline** and its job is **requeued** to
another capable node (bounded by ``max_attempts``) — a dropped node never silently
loses work. Force-push / Sentinel-bypass refusal is enforced one layer down in the
transport, so every dispatched command inherits it.
"""
from __future__ import annotations

from collections import deque
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Callable

from overmind.cluster.registry import Node, NodeRegistry
from overmind.cluster.transport import RemoteTransientError, UnsafeCommandError


@dataclass(slots=True)
class Job:
    repo: str
    needs_engines: tuple[str, ...] = ()
    needs_data: tuple[str, ...] = ()
    command: str | None = None       # remote command (required for remote nodes)
    timeout: float = 900.0
    max_attempts: int = 3
    payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {"repo": self.repo, **self.payload}
        if self.command is not None:
            d["command"] = self.command
        d["timeout"] = self.timeout
        return d


@dataclass(slots=True)
class ScheduleResult:
    results: list[dict] = field(default_factory=list)
    assignments: dict[str, str] = field(default_factory=dict)   # repo -> node
    attempts: dict[str, int] = field(default_factory=dict)       # repo -> attempts made
    errors: list[dict] = field(default_factory=list)
    unschedulable: list[dict] = field(default_factory=list)      # no capable online node
    requeued: list[dict] = field(default_factory=list)           # repo -> from_node (offline)

    @property
    def dispatched(self) -> int:
        return len(self.results)


def select_node(
    registry: NodeRegistry,
    job: Job,
    *,
    exclude: frozenset[str] = frozenset(),
    require_free_capacity: bool = True,
) -> Node | None:
    """Pick the least-loaded capable online node for ``job`` (or None).

    ``exclude`` skips nodes already tried for this job (e.g. one that went offline).
    With ``require_free_capacity=False`` the capacity check is dropped — used to
    distinguish "capable node exists but is full" (wait) from "no capable node at
    all" (unschedulable).
    """
    candidates = [
        n
        for n in registry.capable_online_nodes(
            engines=job.needs_engines, data=job.needs_data
        )
        if n.name not in exclude
    ]
    if require_free_capacity:
        candidates = [n for n in candidates if registry.free_capacity(n.name) > 0]
    if not candidates:
        return None

    def _key(n: Node) -> tuple[float, float, str]:
        st = registry.state(n.name)
        frac = (st.running / n.max_parallel) if n.max_parallel else 1.0
        load = st.load if st.load is not None else 0.0
        return (frac, load, n.name)

    return min(candidates, key=_key)


class JobScheduler:
    """Schedules jobs across a registry's online nodes with load-balancing + requeue."""

    def __init__(self, registry: NodeRegistry) -> None:
        self.registry = registry

    def _capacity(self) -> int:
        cap = sum(self.registry.free_capacity(n.name) + self.registry.state(n.name).running
                  for n in self.registry.online_nodes())
        return max(1, cap)

    def _run_one(self, job: Job, node: Node, runner: Callable[[dict], dict]) -> dict:
        executor = self.registry.executor_for(node.name)
        return executor.run(job.to_dict(), runner)

    def schedule(
        self,
        jobs: list[Job],
        runner: Callable[[dict], dict] | None = None,
    ) -> ScheduleResult:
        """Dispatch ``jobs``, returning per-repo results + assignments.

        ``runner`` is the local in-process verification closure (used by
        ``LocalExecutor``); remote nodes ignore it and run ``job.command``.
        """
        runner = runner or (lambda j: {"repo": j.get("repo"), "verdict": "PASS"})
        out = ScheduleResult()
        if not jobs:
            return out

        pending: deque[Job] = deque(jobs)
        excluded: dict[str, set[str]] = {j.repo: set() for j in jobs}
        out.attempts = {j.repo: 0 for j in jobs}
        in_flight: dict[Future, tuple[Job, Node]] = {}

        with ThreadPoolExecutor(max_workers=self._capacity()) as pool:
            while pending or in_flight:
                waiting_for_capacity: list[Job] = []

                # 1) assign as many pending jobs as free capacity allows
                while pending:
                    job = pending.popleft()
                    excl = frozenset(excluded[job.repo])
                    node = select_node(self.registry, job, exclude=excl)
                    if node is None:
                        # capable node exists but full → wait; else unschedulable
                        any_capable = select_node(
                            self.registry, job, exclude=excl, require_free_capacity=False
                        )
                        if any_capable is not None:
                            waiting_for_capacity.append(job)
                        else:
                            out.unschedulable.append({
                                "repo": job.repo,
                                "needs_engines": list(job.needs_engines),
                                "needs_data": list(job.needs_data),
                                "reason": "no capable online node",
                            })
                        continue
                    out.attempts[job.repo] += 1
                    self.registry.mark_running_delta(node.name, +1)
                    fut = pool.submit(self._run_one, job, node, runner)
                    in_flight[fut] = (job, node)

                # jobs that found a capable-but-full node retry next pass
                pending.extend(waiting_for_capacity)

                if not in_flight:
                    # nothing running and everything left is unschedulable → done
                    break

                # 2) wait for at least one job to finish, then reconcile
                done, _ = wait(list(in_flight), return_when=FIRST_COMPLETED)
                for fut in done:
                    job, node = in_flight.pop(fut)
                    self.registry.mark_running_delta(node.name, -1)
                    self._reconcile(fut, job, node, pending, excluded, out)

        out.results.sort(key=lambda r: str(r.get("repo")))
        return out

    def _reconcile(
        self,
        fut: Future,
        job: Job,
        node: Node,
        pending: deque[Job],
        excluded: dict[str, set[str]],
        out: ScheduleResult,
    ) -> None:
        try:
            result = fut.result()
        except RemoteTransientError as exc:
            # Node dropped mid-job → mark offline, requeue elsewhere (bounded).
            self.registry.set_status(node.name, "offline", detail="transient during job")
            excluded[job.repo].add(node.name)
            out.requeued.append({"repo": job.repo, "from_node": node.name, "reason": str(exc)[:200]})
            still_capable = select_node(
                self.registry, job, exclude=frozenset(excluded[job.repo]),
                require_free_capacity=False,
            )
            if out.attempts[job.repo] < job.max_attempts and still_capable is not None:
                pending.append(job)
            else:
                out.errors.append({
                    "repo": job.repo,
                    "error": f"requeue exhausted after {out.attempts[job.repo]} attempt(s): {exc}",
                })
        except UnsafeCommandError as exc:
            out.errors.append({"repo": job.repo, "error": f"unsafe command refused: {exc}"})
        except Exception as exc:  # noqa: BLE001 — isolate a per-job verification failure
            out.errors.append({"repo": job.repo, "error": f"{type(exc).__name__}: {exc}"})
        else:
            out.results.append(result)
            out.assignments[job.repo] = node.name
